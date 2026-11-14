"""Advisor context building and streaming response helpers."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from app.core.serialization import parse_json_field
from app.db.session import query, query_one


MAX_INPUT_TOKENS_ESTIMATE = 2000
MAX_CONTEXT_MESSAGES = 20
URDU_SCRIPT_RE = r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]"


def estimate_tokens(text: str) -> int:
    """Rough token estimate for lightweight request limiting."""
    import re

    urdu_chars = len(re.findall(URDU_SCRIPT_RE, text or ""))
    other_chars = max(0, len(text or "") - urdu_chars)
    return (urdu_chars + 1) // 2 + (other_chars + 3) // 4


def get_current_season_info(now: datetime | None = None) -> dict[str, str]:
    dt = now or datetime.now()
    month = dt.month
    # Simple seasonal mapping suitable for regional farming guidance.
    if month in (12, 1, 2):
        return {"season": "winter", "phase": "mid"}
    if month in (3, 4):
        return {"season": "spring", "phase": "early"}
    if month in (5, 6):
        return {"season": "summer", "phase": "early"}
    if month in (7, 8, 9):
        return {"season": "rainy", "phase": "mid"}
    return {"season": "autumn", "phase": "late"}


async def load_user_profile(account_id: str) -> dict[str, str]:
    user = await query_one("SELECT full_name FROM users WHERE id = $1", account_id)
    farm = await query_one(
        """
        SELECT district, lat, lng
        FROM farms
        WHERE account_id = $1 AND archived_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        account_id,
    )
    return {
        "fullName": (user or {}).get("full_name") or "Farmer",
        "district": (farm or {}).get("district") or "Unknown",
    }


async def load_farms(account_id: str) -> list[dict[str, Any]]:
    rows = await query(
        """
        SELECT id, name, location, lat, lng, acres, crops, growth_stages
        FROM farms
        WHERE account_id = $1 AND archived_at IS NULL
        ORDER BY created_at DESC
        """,
        account_id,
    )
    farms = []
    for row in rows or []:
        crops_val = parse_json_field(row.get("crops"), row.get("crops"))
        if isinstance(crops_val, list):
            crops_text = ", ".join(str(c) for c in crops_val)
        else:
            crops_text = str(crops_val or "")
        stages = parse_json_field(row.get("growth_stages"), {}) or {}
        stage = "unknown"
        if isinstance(stages, dict) and stages:
            # Use the first tracked stage as a compact summary.
            stage = str(next(iter(stages.values())))
        farms.append(
            {
                "id": str(row.get("id")),
                "name": row.get("name"),
                "location": row.get("location"),
                "lat": float(row.get("lat")) if row.get("lat") is not None else None,
                "lng": float(row.get("lng")) if row.get("lng") is not None else None,
                "acres": float(row.get("acres")) if row.get("acres") is not None else None,
                "crops": crops_text,
                "stage": stage,
            }
        )
    return farms


async def load_recent_summaries(account_id: str, exclude_conversation_id: str) -> str:
    rows = await query(
        """
        SELECT title, summary, updated_at
        FROM advisor_conversations
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
    return "\n".join(lines)


async def load_conversation_history(conversation_id: str) -> str:
    rows = await query(
        """
        SELECT role, content
        FROM advisor_messages
        WHERE conversation_id = $1
        ORDER BY created_at ASC
        LIMIT $2
        """,
        conversation_id,
        MAX_CONTEXT_MESSAGES,
    )
    parts = []
    for row in rows or []:
        role = "Farmer" if row.get("role") == "farmer" else "Advisor"
        parts.append(f"{role}: {row.get('content') or ''}")
    return "\n\n".join(parts)


def _format_farms(farms: list[dict[str, Any]]) -> str:
    if not farms:
        return "No farms registered."
    lines = []
    for farm in farms:
        lines.append(
            f"- {farm.get('name')} ({farm.get('location') or 'location unknown'}): "
            f"crops={farm.get('crops') or 'n/a'}, acres={farm.get('acres') or 'n/a'}, stage={farm.get('stage') or 'n/a'}"
        )
    return "\n".join(lines)


def build_system_prompt(context: dict[str, Any]) -> str:
    season = context.get("currentSeason", "unknown")
    phase = context.get("seasonPhase", "")
    farms_text = _format_farms(context.get("farms") or [])
    summaries = context.get("recentSummaries") or "None"
    return (
        "You are a helpful agricultural advisor for farmers. "
        "Provide practical, safe, and clear guidance based on the provided context. "
        "Do not invent unavailable farm data. If information is missing, ask a short follow-up question.\n\n"
        f"Farmer: {context.get('farmerName', 'Farmer')}\n"
        f"District: {context.get('district', 'Unknown')}\n"
        f"Date: {context.get('currentDate', '')}\n"
        f"Season: {season} ({phase})\n\n"
        "Registered farms:\n"
        f"{farms_text}\n\n"
        "Recent conversation summaries:\n"
        f"{summaries}\n"
    )


async def stream_openai_chat(system_prompt: str, history_text: str, user_message: str) -> AsyncIterator[str]:
    """Stream assistant text deltas from OpenAI-compatible chat completions API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("ADVISOR_MODEL") or "gpt-4o-mini"
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


def check_language_consistency(text: str) -> str:
    """Light cleanup to reduce obvious mixed-language fragments in Urdu responses."""
    import re

    if not text or len(text) < 10:
        return text
    if not re.search(URDU_SCRIPT_RE, text):
        return text
    sentences = [s.strip() for s in re.split(r"[.!?\n\u061F]+", text) if s.strip()]
    kept = []
    for sentence in sentences:
        total = len(re.sub(r"\s+", "", sentence))
        if total == 0:
            continue
        urdu_chars = len(re.findall(URDU_SCRIPT_RE, sentence))
        ratio = urdu_chars / total
        if ratio < 0.3 and len(sentence) > 10:
            continue
        kept.append(sentence)
    if kept and len(kept) < len(sentences):
        return ". ".join(kept)
    return text


async def generate_and_save_summary(conversation_id: str, farmer_message: str, advisor_output: str) -> None:
    """Generate a short conversation summary when model credentials are available."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not advisor_output:
        return

    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("ADVISOR_MODEL") or "gpt-4o-mini"
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Summarize this farmer-advisor exchange in 1-2 sentences focusing on the question and key advice.",
            },
            {
                "role": "user",
                "content": f"Farmer: {farmer_message}\n\nAdvisor: {advisor_output[:500]}",
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
                "UPDATE advisor_conversations SET summary = $1, summary_updated_at = now() WHERE id = $2",
                summary,
                conversation_id,
            )
    except Exception:
        # Summary generation is best-effort and should not block chat completion.
        return
