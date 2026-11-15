"""App control conversation and chat API routes."""

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
from app.core.serialization import parse_json_field, to_jsonable
from app.db.session import execute, query, query_one
from app.models.app_control import (
    AppControlChatRequest,
    CreateAppControlConversationRequest,
    RenameAppControlConversationRequest,
)
from app.services.app_control import (
    estimate_tokens,
    generate_and_save_summary,
    load_conversation_history,
    normalize_output,
)
from app.services.ai.agent import stream_agent
from app.services.ai.guardrails import sanitize_input
from app.services.app_control_agent import build_app_control_agent

router = APIRouter(prefix="/app-control", tags=["app-control"])

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}


def _parse_page_context(request: Request) -> tuple[str, dict[str, Any]]:
    header = request.headers.get("X-Page-Context")
    if not header:
        return "", {}
    try:
        parsed = json.loads(header)
        if not isinstance(parsed, dict):
            return "", {}
        current_path = parsed.get("currentPath") if isinstance(parsed.get("currentPath"), str) else ""
        page_state = parsed.get("pageState") if isinstance(parsed.get("pageState"), dict) else {}
        return current_path, page_state
    except Exception:
        return "", {}


def _normalize_message_row(row: dict[str, Any]) -> dict[str, Any]:
    attachments = parse_json_field(row.get("attachments"), row.get("attachments"))
    if not isinstance(attachments, list):
        attachments = []
    return {
        "id": row.get("id"),
        "role": row.get("role"),
        "content": row.get("content"),
        "attachments": attachments,
        "created_at": row.get("created_at"),
    }


@router.get("/conversations")
async def list_conversations(session: dict = Depends(require_session)):
    try:
        rows = await query(
            """
            SELECT id, title, language, created_at, updated_at
            FROM app_control_conversations
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
        parsed = CreateAppControlConversationRequest.model_validate(body or {})
        row = await query_one(
            """
            INSERT INTO app_control_conversations (account_id, title, language)
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
            FROM app_control_conversations
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
        parsed = RenameAppControlConversationRequest.model_validate(body or {})
        row = await query_one(
            """
            UPDATE app_control_conversations
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
            "DELETE FROM app_control_conversations WHERE id = $1 AND account_id = $2",
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
            "SELECT id FROM app_control_conversations WHERE id = $1 AND account_id = $2",
            conversation_id,
            session["accountId"],
        )
        if not conv:
            return error_response("server_error", "Conversation not found.", 404)

        rows = await query(
            """
            SELECT id, role, content, attachments, created_at
            FROM app_control_messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            """,
            conversation_id,
        )
        messages = [_normalize_message_row(r) for r in (rows or [])]
        return success({"messages": to_jsonable(messages)})
    except Exception as err:
        return error_response("server_error", str(err), 500)


async def _extract_chat_input(request: Request) -> tuple[str, str | None, list[dict[str, Any]]]:
    content_type = (request.headers.get("content-type") or "").lower()
    attachments: list[dict[str, Any]] = []

    if "multipart/form-data" in content_type:
        form = await request.form()
        message = str(form.get("message") or "").strip()
        conversation_id = form.get("conversationId")
        conv_id = str(conversation_id).strip() if isinstance(conversation_id, str) and conversation_id.strip() else None
        # Attachment binaries are accepted for compatibility; store lightweight metadata only.
        for value in form.getlist("attachments"):
            filename = getattr(value, "filename", None)
            content_type_val = getattr(value, "content_type", None) or "application/octet-stream"
            if filename:
                attachments.append({"type": content_type_val, "url": "", "name": str(filename), "size": 0})
        return message, conv_id, attachments

    body = await read_json_body(request)
    parsed = AppControlChatRequest.model_validate(body or {})
    return parsed.message.strip(), parsed.conversationId, []


async def _ensure_conversation(account_id: str, conversation_id: str | None, first_message: str) -> str | None:
    if conversation_id:
        return conversation_id
    row = await query_one(
        """
        INSERT INTO app_control_conversations (account_id, title, language)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        account_id,
        (first_message[:60] or "New conversation"),
        "en",
    )
    return str(row["id"]) if row and row.get("id") else None


@router.post("/chat")
async def app_control_chat(request: Request, session: dict = Depends(require_session)):
    try:
        ip = client_ip(request)
        now_ms = int(time.time() * 1000)
        if not rate_limit.hit("app-control-chat:ip", ip, 30, 3600000, now_ms=now_ms):
            return error_response("rate_limited", "Too many requests. Try again in a moment.", 429)
        if not rate_limit.hit("app-control-chat:acct", session["accountId"], 50, 3600000, now_ms=now_ms):
            return error_response("rate_limited", "You've used this feature a lot today. Try again later.", 429)

        message, requested_conversation_id, attachments = await _extract_chat_input(request)
        message = sanitize_input(message).strip()
        if not message:
            return error_response("validation_error", "Message is required.", 422)
        if estimate_tokens(message) > 2000:
            return error_response("validation_error", "Your message is too long. Please keep it under 2000 characters.", 422)

        conversation_id = await _ensure_conversation(session["accountId"], requested_conversation_id, message)
        if not conversation_id:
            return error_response("server_error", "Could not create conversation.", 500)

        if requested_conversation_id:
            owned = await query_one(
                "SELECT id FROM app_control_conversations WHERE id = $1 AND account_id = $2",
                conversation_id,
                session["accountId"],
            )
            if not owned:
                return error_response("not_found", "Conversation not found.", 404)

        current_path, page_state = _parse_page_context(request)
        history_text = await load_conversation_history(conversation_id)
        agent = build_app_control_agent(session["accountId"], current_path, page_state)
        agents = {"AppControl": agent}
        now = datetime.now(timezone.utc)

        async def event_stream() -> AsyncIterator[bytes]:
            accumulated = ""
            finished = False

            async def finish(output_text: str) -> None:
                nonlocal finished
                if finished:
                    return
                finished = True
                cleaned = normalize_output(output_text)
                try:
                    await execute(
                        """
                        INSERT INTO app_control_messages (conversation_id, role, content, attachments)
                        VALUES ($1, $2, $3, $4::jsonb), ($1, $5, $6, NULL)
                        """,
                        conversation_id,
                        "farmer",
                        message,
                        json.dumps(attachments),
                        "agent",
                        cleaned,
                    )
                    await execute(
                        """
                        UPDATE app_control_conversations
                        SET title = CASE WHEN title = 'New conversation' OR title = '' THEN $1 ELSE title END,
                            updated_at = $2
                        WHERE id = $3
                        """,
                        (message[:60] or "New conversation"),
                        now,
                        conversation_id,
                    )
                    await generate_and_save_summary(conversation_id, message, cleaned)
                except Exception:
                    pass

            try:
                opening = json.dumps({"type": "conversation", "id": conversation_id})
                yield f"data: {opening}\n\n".encode("utf-8")

                async for event in stream_agent(agents, "AppControl", message, history_text):
                    event_type = event.get("type")
                    if event_type == "text":
                        accumulated += str(event.get("delta") or "")
                        payload = json.dumps({"type": "text", "delta": event.get("delta") or ""})
                        yield f"data: {payload}\n\n".encode("utf-8")
                    elif event_type in ("navigation_button", "action_card"):
                        payload = json.dumps({"type": event_type, **{k: v for k, v in event.items() if k != "type"}})
                        yield f"data: {payload}\n\n".encode("utf-8")
                    elif event_type == "done":
                        cleaned_output = normalize_output(str(event.get("output") or accumulated))
                        await finish(cleaned_output)
                        done_payload = json.dumps({"type": "done", "output": cleaned_output})
                        yield f"data: {done_payload}\n\n".encode("utf-8")
                    elif event_type == "error":
                        await finish(accumulated)
                        error_payload = json.dumps(
                            {
                                "type": "error",
                                "message": event.get("message")
                                or "App control is temporarily unavailable. Please try again in a moment.",
                            }
                        )
                        yield f"data: {error_payload}\n\n".encode("utf-8")
            except Exception:
                await finish(accumulated)
                error_payload = json.dumps(
                    {"type": "error", "message": "App control is temporarily unavailable. Please try again in a moment."}
                )
                yield f"data: {error_payload}\n\n".encode("utf-8")

        return StreamingResponse(event_stream(), headers=SSE_HEADERS)
    except Exception as err:
        msg = str(err)
        if "OPENAI_API_KEY" in msg or "LLM_API_KEY" in msg:
            return error_response("server_error", "App control is temporarily unavailable. Please try again in a moment.", 503)
        if "validation error" in msg.lower() or "Message is required" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", "App control is temporarily unavailable. Please try again in a moment.", 503)
