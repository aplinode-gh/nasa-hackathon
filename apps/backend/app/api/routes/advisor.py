"""Advisor conversation and chat API routes."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core import rate_limit
from app.core.deps import require_session
from app.core.http import client_ip, error_response, read_json_body, success
from app.core.serialization import to_jsonable
from app.db.session import execute, query, query_one
from app.models.advisor import AdvisorChatRequest, CreateConversationRequest, RenameConversationRequest
from app.services.advisor import (
    MAX_CONTEXT_MESSAGES,
    build_system_prompt,
    check_language_consistency,
    estimate_tokens,
    generate_and_save_summary,
    get_current_season_info,
    load_conversation_history,
    load_farms,
    load_recent_summaries,
    load_user_profile,
    stream_openai_chat,
)

router = APIRouter(prefix="/advisor", tags=["advisor"])

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}


@router.get("/conversations")
async def list_conversations(session: dict = Depends(require_session)):
    try:
        rows = await query(
            """
            SELECT id, title, language, created_at, updated_at
            FROM advisor_conversations
            WHERE account_id = $1
            ORDER BY updated_at DESC
            """,
            session["accountId"],
        )
        return success({"conversations": to_jsonable(rows or [])})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/conversations")
async def create_conversation(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = CreateConversationRequest.model_validate(body or {})
        row = await query_one(
            """
            INSERT INTO advisor_conversations (account_id, title, language)
            VALUES ($1, $2, $3)
            RETURNING id, title, language, created_at, updated_at
            """,
            session["accountId"],
            "New conversation",
            parsed.language,
        )
        if not row:
            return error_response("server_error", "Could not create conversation.", 500)
        return success({"conversation": to_jsonable(row)}, status_code=201)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", str(err), 500)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, session: dict = Depends(require_session)):
    try:
        row = await query_one(
            """
            SELECT id, title, language, created_at, updated_at
            FROM advisor_conversations
            WHERE id = $1 AND account_id = $2
            """,
            conversation_id,
            session["accountId"],
        )
        if not row:
            return error_response("server_error", "Conversation not found.", 404)
        return success({"conversation": to_jsonable(row)})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(conversation_id: str, request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = RenameConversationRequest.model_validate(body or {})
        row = await query_one(
            """
            UPDATE advisor_conversations
            SET title = $1, updated_at = $2
            WHERE id = $3 AND account_id = $4
            RETURNING id, title, language, created_at, updated_at
            """,
            parsed.title,
            datetime.now(timezone.utc),
            conversation_id,
            session["accountId"],
        )
        if not row:
            return error_response("server_error", "Conversation not found.", 404)
        return success({"conversation": to_jsonable(row)})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", str(err), 500)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, session: dict = Depends(require_session)):
    try:
        await execute(
            "DELETE FROM advisor_conversations WHERE id = $1 AND account_id = $2",
            conversation_id,
            session["accountId"],
        )
        return success({"deleted": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/messages/{conversation_id}")
async def list_messages(conversation_id: str, session: dict = Depends(require_session)):
    try:
        conv = await query_one(
            "SELECT id FROM advisor_conversations WHERE id = $1 AND account_id = $2",
            conversation_id,
            session["accountId"],
        )
        if not conv:
            return error_response("server_error", "Conversation not found.", 404)

        messages = await query(
            """
            SELECT id, role, content, created_at
            FROM advisor_messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            """,
            conversation_id,
        )
        return success({"messages": to_jsonable(messages or [])})
    except Exception as err:
        return error_response("server_error", str(err), 500)


async def _ensure_conversation(account_id: str, conversation_id: str | None, first_message: str) -> str | None:
    if conversation_id:
        return conversation_id
    row = await query_one(
        """
        INSERT INTO advisor_conversations (account_id, title, language)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        account_id,
        (first_message[:60] or "New conversation"),
        "en",
    )
    return str(row["id"]) if row and row.get("id") else None


@router.post("/chat")
async def advisor_chat(request: Request, session: dict = Depends(require_session)):
    try:
        ip = client_ip(request)
        now_ms = int(time.time() * 1000)
        # Lightweight request throttling per IP and account.
        if not rate_limit.hit("advisor-chat:ip", ip, 30, 3600000, now_ms=now_ms):
            return error_response("rate_limited", "Too many requests. Try again in a moment.", 429)
        if not rate_limit.hit("advisor-chat:acct", session["accountId"], 50, 3600000, now_ms=now_ms):
            return error_response("rate_limited", "You've used the advisor a lot today. Try again later.", 429)

        body = await read_json_body(request)
        parsed = AdvisorChatRequest.model_validate(body or {})
        message = parsed.message.strip()
        if estimate_tokens(message) > 2000:
            return error_response("validation_error", "Your message is too long. Please keep it under 2000 characters.", 422)

        conversation_id = await _ensure_conversation(session["accountId"], parsed.conversationId, message)
        if not conversation_id:
            return error_response("server_error", "Could not create conversation.", 500)

        # Ensure the conversation belongs to the current account if client supplied an id.
        if parsed.conversationId:
            owned = await query_one(
                "SELECT id FROM advisor_conversations WHERE id = $1 AND account_id = $2",
                conversation_id,
                session["accountId"],
            )
            if not owned:
                return error_response("not_found", "Conversation not found.", 404)

        history_text = await load_conversation_history(conversation_id)
        profile, farms, recent_summaries = await asyncio_gather_profile(session["accountId"], conversation_id)
        season_info = get_current_season_info()
        now = datetime.now(timezone.utc)

        context = {
            "accountId": session["accountId"],
            "farmerName": profile.get("fullName"),
            "language": "en",
            "farms": farms,
            "currentSeason": season_info.get("season"),
            "seasonPhase": season_info.get("phase"),
            "currentDate": now.strftime("%B %d, %Y"),
            "district": profile.get("district"),
            "recentSummaries": recent_summaries,
        }
        system_prompt = build_system_prompt(context)

        async def event_stream() -> AsyncIterator[bytes]:
            accumulated = ""
            finished = False

            async def finish(output_text: str) -> None:
                nonlocal finished
                if finished:
                    return
                finished = True
                cleaned = check_language_consistency(output_text)
                try:
                    await execute(
                        """
                        INSERT INTO advisor_messages (conversation_id, role, content)
                        VALUES ($1, $2, $3), ($1, $4, $5)
                        """,
                        conversation_id,
                        "farmer",
                        message,
                        "advisor",
                        cleaned,
                    )
                    await execute(
                        "UPDATE advisor_conversations SET updated_at = $1 WHERE id = $2",
                        now,
                        conversation_id,
                    )
                    await generate_and_save_summary(conversation_id, message, cleaned)
                except Exception:
                    # Stream completion should still return the generated response.
                    pass

            try:
                opening = json.dumps({"type": "conversation", "id": conversation_id})
                yield f"data: {opening}\n\n".encode("utf-8")

                async for delta in stream_openai_chat(system_prompt, history_text, message):
                    accumulated += delta
                    payload = json.dumps({"type": "text", "delta": delta})
                    yield f"data: {payload}\n\n".encode("utf-8")

                cleaned_output = check_language_consistency(accumulated)
                await finish(cleaned_output)
                done_payload = json.dumps({"type": "done", "output": cleaned_output})
                yield f"data: {done_payload}\n\n".encode("utf-8")
            except Exception as err:
                await finish(accumulated)
                error_payload = json.dumps(
                    {"type": "error", "message": "Advisor service is temporarily unavailable. Please try again in a moment."}
                )
                yield f"data: {error_payload}\n\n".encode("utf-8")

        return StreamingResponse(event_stream(), headers=SSE_HEADERS)
    except Exception as err:
        msg = str(err)
        if "OPENAI_API_KEY" in msg:
            return error_response("server_error", "Advisor service is temporarily unavailable. Please try again in a moment.", 503)
        if "validation error" in msg.lower() or "Enter a message" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", "Advisor service is temporarily unavailable. Please try again in a moment.", 503)


async def asyncio_gather_profile(account_id: str, conversation_id: str):
    # Sequential awaits keep dependencies simple and avoid extra task plumbing.
    profile = await load_user_profile(account_id)
    farms = await load_farms(account_id)
    summaries = await load_recent_summaries(account_id, conversation_id)
    return profile, farms, summaries
