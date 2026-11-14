"""App control chat context and streaming helpers."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from app.db.session import query, query_one
from app.services.advisor import check_language_consistency, estimate_tokens


MAX_CONTEXT_MESSAGES = 20


async def load_recent_summaries(account_id: str, exclude_conversation_id: str | None) -> str:
    if not exclude_conversation_id:
        return "None"
    rows = await query(
        """
        SELECT title, summary, updated_at
        FROM app_control_conversations
        WHERE account_id = $1
          AND summary IS NOT NULL
          AND id <> $2
        ORDER BY updated_at DESC
        LIMIT 3
        """,
        account_id,
        exclude_conversation_id,
    )
    lines = []
    for row in rows or []:
        updated = row.get("updated_at")
        try:
            date_label = updated.strftime("%b %d") if hasattr(updated, "strftime") else str(updated)[:10]
        except Exception:
            date_label = ""
        title = row.get("title") or "Conversation"
        summary = row.get("summary") or ""
        lines.append(f'- "{title}" ({date_label}): {summary}')
    return "\n".join(lines) or "None"


async def load_conversation_history(conversation_id: str) -> str:
    rows = await query(
        """
        SELECT role, content
        FROM app_control_messages
        WHERE conversation_id = $1
        ORDER BY created_at ASC
        LIMIT $2
        """,
        conversation_id,
        MAX_CONTEXT_MESSAGES,
    )
    parts = []
    for row in rows or []:
        role = "Farmer" if row.get("role") == "farmer" else "Assistant"
        parts.append(f"{role}: {row.get('content') or ''}")
    return "\n\n".join(parts)


async def load_farms_summary(account_id: str) -> str:
    rows = await query(
        """
        SELECT name, location, district, acres, crops, growth_stages
        FROM farms
        WHERE account_id = $1 AND archived_at IS NULL
        ORDER BY created_at DESC
        LIMIT 20
        """,
        account_id,
    )
    if not rows:
        return "No farms registered."
    lines = []
    for farm in rows:
        crops = farm.get("crops")
        if isinstance(crops, str):
            try:
                parsed = json.loads(crops)
                if isinstance(parsed, list):
                    crops = ", ".join(str(x) for x in parsed)
            except Exception:
                pass
        if isinstance(crops, list):
            crops = ", ".join(str(x) for x in crops)
        lines.append(
            f"- {farm.get('name')} ({farm.get('location') or farm.get('district') or 'location unknown'}): "
            f"{farm.get('acres') or 'n/a'} acres, crops: {crops or 'n/a'}"
        )
    return "\n".join(lines)


async def load_recent_records_summary(account_id: str) -> str:
    rows = await query(
        """
        SELECT r.type, r.event_date, r.title, f.name AS farm_name
        FROM records r
        JOIN farms f ON f.id = r.farm_id
        WHERE r.account_id = $1
        ORDER BY r.event_date DESC, r.created_at DESC
        LIMIT 10
        """,
        account_id,
    )
    if not rows:
        return "No recent records."
    lines = []
    for row in rows:
        title = row.get("title") or row.get("type") or "activity"
        lines.append(f"- [{row.get('farm_name')}] {title} ({row.get('type')}) on {row.get('event_date')}")
    return "\n".join(lines)


async def build_app_control_system_prompt(
    account_id: str,
    conversation_id: str | None,
    current_path: str = "",
    page_state: dict[str, Any] | None = None,
) -> str:
    farms_text = await load_farms_summary(account_id)
    records_text = await load_recent_records_summary(account_id)
    summaries = await load_recent_summaries(account_id, conversation_id)
    page_state = page_state or {}
    return (
        "You are a helpful in-app assistant for a farming dashboard. "
        "Help the user understand and manage their app data, answer questions clearly, and suggest where to go in the app when useful. "
        "Use the provided account context when answering. Do not invent farm names, records, prices, or weather details that are not in context. "
        "If the user asks for an action you cannot perform directly, explain the steps in the app.\n\n"
        f"Current page: {current_path or 'unknown'}\n"
        f"Page state: {json.dumps(page_state, default=str)[:2000]}\n"
        f"Current date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}\n\n"
        "Registered farms:\n"
        f"{farms_text}\n\n"
        "Recent activity records:\n"
        f"{records_text}\n\n"
        "Recent conversation summaries:\n"
        f"{summaries}\n"
    )


async def stream_openai_chat(system_prompt: str, history_text: str, user_message: str) -> AsyncIterator[str]:
    """Stream assistant text deltas from an OpenAI-compatible chat completions API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("ADVISOR_MODEL") or os.getenv("APP_CONTROL_MODEL") or "gpt-4o-mini"
    url = f"{base_url}/chat/completions"

    messages = [{"role": "system", "content": system_prompt}]
    if history_text:
        messages.append({"role": "user", "content": f"Conversation so far:\n{history_text}"})
    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.4,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except Exception:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = (choices[0].get("delta") or {}).get("content")
                if delta:
                    yield delta


async def generate_and_save_summary(conversation_id: str, user_message: str, assistant_output: str) -> None:
    """Generate a short conversation summary when model credentials are available."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not assistant_output:
        return

    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("ADVISOR_MODEL") or os.getenv("APP_CONTROL_MODEL") or "gpt-4o-mini"
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Summarize this exchange in 1-2 sentences focusing on the request and the outcome.",
            },
            {
                "role": "user",
                "content": f"User: {user_message}\n\nAssistant: {assistant_output[:500]}",
            },
        ],
        "max_tokens": 100,
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        summary = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if summary:
            await query(
                "UPDATE app_control_conversations SET summary = $1, updated_at = now() WHERE id = $2",
                summary,
                conversation_id,
            )
    except Exception:
        return


def normalize_output(text: str) -> str:
    cleaned = check_language_consistency(text)
    return cleaned.strip() if cleaned else cleaned
