"""Disease detection API routes: scans, chat sessions, and messages."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse

from app.core.deps import require_session
from app.core.http import error_response, read_json_body, success
from app.core.serialization import parse_json_field, to_jsonable
from app.db.session import execute, query, query_one
from app.models.detect import CreateDetectChatRequest, DetectChatRequest, SaveScanRequest
from app.services.ai.llm import get_llm_config, llm_configured
from app.services.ai.sdk_runtime import stream_sdk_agent
from app.services.detect import diagnose_image, fallback_chat_reply
from agents import Agent

router = APIRouter(prefix="/detect", tags=["detect"])

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
HISTORY_LIMIT = 20

CLOUDINARY_UPLOAD_URL = "https://api.cloudinary.com/v1_1/{cloud}/image/upload"


def _cloudinary_configured() -> bool:
    return bool(
        os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


async def _upload_to_cloudinary(data: bytes, account_id: str, filename: str) -> str:
    """Upload image bytes to Cloudinary and return the secure URL."""
    import base64
    import hashlib
    import time

    cloud = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    api_key = os.getenv("CLOUDINARY_API_KEY", "")
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "")

    timestamp = str(int(time.time()))
    folder = f"scans/user_{account_id}"
    public_id = f"scan_{uuid4().hex[:8]}"

    # Signature: sort params (excluding file, api_key, resource_type) alphabetically
    to_sign = f"folder={folder}&public_id={public_id}&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(to_sign.encode("utf-8")).hexdigest()

    # data URI upload (no extra dependency needed)
    mime = "image/jpeg"
    lower = (filename or "").lower()
    if lower.endswith(".png"):
        mime = "image/png"
    elif lower.endswith(".webp"):
        mime = "image/webp"
    data_uri = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    form = {
        "file": data_uri,
        "api_key": api_key,
        "timestamp": timestamp,
        "signature": signature,
        "folder": folder,
        "public_id": public_id,
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(CLOUDINARY_UPLOAD_URL.format(cloud=cloud), data=form)
        resp.raise_for_status()
        payload = resp.json()

    secure_url = payload.get("secure_url")
    if not secure_url:
        raise RuntimeError("Cloudinary upload returned no URL")
    return secure_url



def _scan_out(row: dict[str, Any]) -> dict[str, Any]:
    steps = parse_json_field(row.get("treatment_steps"), [])
    if not isinstance(steps, list):
        steps = []
    return {
        "id": str(row.get("id")),
        "diseaseName": row.get("disease_name"),
        "confidence": float(row.get("confidence") or 0),
        "severity": row.get("severity"),
        "crop": row.get("crop"),
        "causes": row.get("causes"),
        "steps": steps,
        "rescanTiming": row.get("rescan_timing"),
        "caution": row.get("caution"),
        "imageUrl": row.get("image_url"),
        "createdAt": row.get("created_at"),
        "farmId": str(row["farm_id"]) if row.get("farm_id") else None,
        "farmName": row.get("farm_name"),
        "saveStatus": "saved" if row.get("farm_id") else "not_saved",
    }


@router.get("/history")
async def scan_history(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        try:
            limit = int(qp.get("limit", str(HISTORY_LIMIT)))
        except Exception:
            return error_response("validation_error", "Invalid query", 422)
        if limit <= 0 or limit > 50:
            return error_response("validation_error", "Invalid query", 422)
        cursor = qp.get("cursor")

        conditions = ["ds.account_id = $1"]
        values: list[Any] = [session["accountId"]]
        idx = 2
        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
            except ValueError:
                return error_response("validation_error", "Invalid cursor", 422)
            conditions.append(f"ds.created_at < ${idx}")
            values.append(cursor_dt)
            idx += 1

        rows = await query(
            f"""
            SELECT ds.*, f.name AS farm_name
            FROM detect_scans ds
            LEFT JOIN farms f ON f.id = ds.farm_id
            WHERE {' AND '.join(conditions)}
            ORDER BY ds.created_at DESC
            LIMIT ${idx}
            """,
            *values,
            limit + 1,
        )
        rows = rows or []
        has_more = len(rows) > limit
        data = rows[:limit] if has_more else rows
        next_cursor = data[-1].get("created_at") if has_more and data else None
        return success(
            {
                "scans": to_jsonable([_scan_out(row) for row in data]),
                "nextCursor": to_jsonable(next_cursor),
            }
        )
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("")
async def analyze_scan(
    request: Request,
    image: UploadFile = File(...),
    session: dict = Depends(require_session),
):
    try:
        content_type = (image.content_type or "").lower()
        if not content_type.startswith("image/"):
            return error_response("validation_error", "Please upload an image file.", 415)

        data = await image.read()
        if not data:
            return error_response("validation_error", "The uploaded image is empty.", 422)
        if len(data) > MAX_UPLOAD_BYTES:
            return error_response("payload_too_large", "Image must be smaller than 10 MB.", 413)

        diagnosis = await diagnose_image(data, image.filename or "")
        if diagnosis.get("noDiagnosis"):
            return success({"noDiagnosis": True})

        if not _cloudinary_configured():
            return error_response(
                "server_error",
                "Image storage is not configured. Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET.",
                503,
            )

        scan_id = str(uuid4())
        try:
            image_url = await _upload_to_cloudinary(data, session["accountId"], image.filename or "scan.jpg")
        except Exception as err:
            return error_response("server_error", f"Image storage error: {err}", 503)

        row = await query_one(
            """
            INSERT INTO detect_scans (
              id, account_id, disease_name, confidence, severity, crop, causes,
              treatment_steps, rescan_timing, caution, image_url, image_path
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            scan_id,
            session["accountId"],
            diagnosis["diseaseName"],
            diagnosis["confidence"],
            diagnosis["severity"],
            diagnosis["crop"],
            diagnosis["causes"],
            json.dumps(diagnosis.get("steps") or []),
            diagnosis.get("rescanTiming") or "",
            diagnosis.get("caution") or "",
            image_url,
            None,
        )
        if not row:
            return error_response("server_error", "Failed to save scan", 500)

        return success(
            {
                "scanId": scan_id,
                "diseaseName": diagnosis["diseaseName"],
                "confidence": diagnosis["confidence"],
                "severity": diagnosis["severity"],
                "crop": diagnosis["crop"],
                "causes": diagnosis["causes"],
                "steps": diagnosis.get("steps") or [],
                "rescanTiming": diagnosis.get("rescanTiming") or "",
                "caution": diagnosis.get("caution") or "",
                "imageUrl": image_url,
            },
            status_code=201,
        )
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/image/{scan_id}")
async def scan_image(scan_id: str, session: dict = Depends(require_session)):
    row = await query_one(
        "SELECT image_url, image_path FROM detect_scans WHERE id = $1 AND account_id = $2",
        scan_id,
        session["accountId"],
    )
    if not row:
        return error_response("not_found", "Image not found", 404)

    image_url = row.get("image_url")
    if image_url and str(image_url).startswith("http"):
        return RedirectResponse(url=str(image_url), status_code=307)

    image_path = row.get("image_path")
    if image_path:
        from pathlib import Path
        from fastapi.responses import FileResponse

        path = Path(str(image_path))
        if path.exists():
            return FileResponse(path)

    return error_response("not_found", "Image not found", 404)


@router.get("/chats")
async def list_chats(session: dict = Depends(require_session)):
    try:
        rows = await query(
            """
            SELECT id, title, scan_id, updated_at
            FROM detect_chats
            WHERE account_id = $1
            ORDER BY updated_at DESC
            LIMIT 50
            """,
            session["accountId"],
        )
        chats = [
            {
                "id": str(row.get("id")),
                "title": row.get("title"),
                "scanId": str(row["scan_id"]) if row.get("scan_id") else None,
                "updatedAt": row.get("updated_at"),
            }
            for row in (rows or [])
        ]
        return success({"chats": to_jsonable(chats)})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/chats/{chat_id}")
async def get_chat(chat_id: str, session: dict = Depends(require_session)):
    try:
        chat = await query_one(
            "SELECT id, title, scan_id, updated_at FROM detect_chats WHERE id = $1 AND account_id = $2",
            chat_id,
            session["accountId"],
        )
        if not chat:
            return error_response("not_found", "Chat not found", 404)

        scan = None
        if chat.get("scan_id"):
            row = await query_one(
                """
                SELECT id, disease_name, confidence, severity, crop, causes, treatment_steps,
                       rescan_timing, caution, image_url, created_at
                FROM detect_scans WHERE id = $1
                """,
                chat["scan_id"],
            )
            if row:
                scan = _scan_out(row)

        return success(
            {
                "chat": {
                    "id": str(chat["id"]),
                    "title": chat.get("title"),
                    "scanId": str(chat["scan_id"]) if chat.get("scan_id") else None,
                    "updatedAt": chat.get("updated_at"),
                },
                "scan": scan,
            }
        )
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, session: dict = Depends(require_session)):
    try:
        chat = await query_one(
            "SELECT id FROM detect_chats WHERE id = $1 AND account_id = $2",
            chat_id,
            session["accountId"],
        )
        if not chat:
            return error_response("not_found", "Chat not found", 404)
        await execute("DELETE FROM detect_chats WHERE id = $1 AND account_id = $2", chat_id, session["accountId"])
        return success({"deleted": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/chats")
async def create_chat(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = CreateDetectChatRequest.model_validate(body or {})

        title = "Leaf scan"
        if parsed.scanId:
            scan = await query_one(
                "SELECT disease_name FROM detect_scans WHERE id = $1 AND account_id = $2",
                parsed.scanId,
                session["accountId"],
            )
            if not scan:
                return error_response("not_found", "Scan not found", 404)
            title = scan.get("disease_name") or title

        row = await query_one(
            """
            INSERT INTO detect_chats (account_id, scan_id, title)
            VALUES ($1, $2, $3)
            RETURNING id, title, scan_id, updated_at
            """,
            session["accountId"],
            parsed.scanId,
            title,
        )
        if not row:
            return error_response("server_error", "Failed to create chat", 500)
        return success({"chatId": str(row["id"])}, status_code=201)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.get("/messages/{chat_id}")
async def list_messages(chat_id: str, session: dict = Depends(require_session)):
    try:
        chat = await query_one(
            "SELECT id FROM detect_chats WHERE id = $1 AND account_id = $2",
            chat_id,
            session["accountId"],
        )
        if not chat:
            return error_response("not_found", "Chat not found", 404)

        rows = await query(
            "SELECT id, role, content, created_at FROM detect_messages WHERE chat_id = $1 ORDER BY created_at ASC",
            chat_id,
        )
        return success({"messages": to_jsonable(rows or [])})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/chat")
async def detect_chat(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = DetectChatRequest.model_validate(body or {})
        message = parsed.message.strip()
        if not message:
            return error_response("validation_error", "Enter a message", 422)

        chat = await query_one(
            """
            SELECT c.id, c.scan_id, ds.disease_name, ds.crop, ds.causes,
                   ds.treatment_steps, ds.rescan_timing, ds.caution
            FROM detect_chats c
            LEFT JOIN detect_scans ds ON ds.id = c.scan_id
            WHERE c.id = $1 AND c.account_id = $2
            """,
            parsed.chatId,
            session["accountId"],
        )
        if not chat:
            return error_response("not_found", "Chat not found", 404)

        await execute(
            "INSERT INTO detect_messages (chat_id, role, content) VALUES ($1, 'farmer', $2)",
            parsed.chatId,
            message,
        )

        diagnosis = {
            "disease_name": chat.get("disease_name"),
            "crop": chat.get("crop"),
            "causes": chat.get("causes"),
            "treatment_steps": parse_json_field(chat.get("treatment_steps"), []),
            "rescan_timing": chat.get("rescan_timing"),
            "caution": chat.get("caution"),
        }
        history = await query(
            "SELECT role, content FROM detect_messages WHERE chat_id = $1 ORDER BY created_at ASC LIMIT 20",
            parsed.chatId,
        )
        history_text = "\n".join(
            f"{'Farmer' if row.get('role') == 'farmer' else 'Detect'}: {row.get('content')}" for row in (history or [])
        )
        system_prompt = (
            "You are a crop disease assistant. Answer the farmer's follow-up questions about "
            f"this scan. Disease: {diagnosis['disease_name'] or 'unknown'}. Crop: {diagnosis['crop'] or 'unknown'}. "
            f"Causes: {diagnosis['causes'] or 'unknown'}. "
            "Give practical, safe advice. Be concise. Do not invent lab results."
        )

        agent = Agent(
            name="Detect",
            instructions=system_prompt,
            model=get_llm_config("detect").model,
        )

        async def event_stream() -> AsyncIterator[bytes]:
            accumulated = ""
            try:
                if llm_configured("detect"):
                    async for event in stream_sdk_agent(agent, message, history=history_text, feature="detect"):
                        if event.get("type") == "text":
                            delta = str(event.get("delta") or "")
                            accumulated += delta
                            yield f"data: {json.dumps({'type': 'text', 'delta': delta})}\n\n".encode("utf-8")
                        elif event.get("type") == "done":
                            accumulated = str(event.get("output") or accumulated)
                        elif event.get("type") == "error":
                            raise RuntimeError(str(event.get("message") or "detect chat failed"))
                else:
                    accumulated = fallback_chat_reply(diagnosis)
                    for chunk in accumulated.split(" "):
                        yield f"data: {json.dumps({'type': 'text', 'delta': chunk + ' '})}\n\n".encode("utf-8")
            except Exception:
                accumulated = accumulated or fallback_chat_reply(diagnosis)

            if accumulated:
                await execute(
                    "INSERT INTO detect_messages (chat_id, role, content) VALUES ($1, 'detect', $2)",
                    parsed.chatId,
                    accumulated,
                )
                await execute(
                    "UPDATE detect_chats SET updated_at = $1 WHERE id = $2",
                    datetime.now(timezone.utc),
                    parsed.chatId,
                )
            yield f"data: {json.dumps({'type': 'done', 'output': accumulated})}\n\n".encode("utf-8")

        return StreamingResponse(event_stream(), headers=SSE_HEADERS)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Enter a message" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.post("/save")
async def save_scan(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = SaveScanRequest.model_validate(body or {})

        scan = await query_one(
            "SELECT id FROM detect_scans WHERE id = $1 AND account_id = $2",
            parsed.scanId,
            session["accountId"],
        )
        if not scan:
            return error_response("not_found", "Scan not found", 404)
        farm = await query_one(
            "SELECT id FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL",
            parsed.farmId,
            session["accountId"],
        )
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        await execute("UPDATE detect_scans SET farm_id = $1 WHERE id = $2", parsed.farmId, parsed.scanId)
        return success({"ok": True})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, session: dict = Depends(require_session)):
    try:
        scan = await query_one(
            "SELECT image_path FROM detect_scans WHERE id = $1 AND account_id = $2",
            scan_id,
            session["accountId"],
        )
        if not scan:
            return error_response("not_found", "Scan not found", 404)

        await execute("DELETE FROM detect_scans WHERE id = $1 AND account_id = $2", scan_id, session["accountId"])
        image_path = scan.get("image_path")
        if image_path:
            try:
                import asyncio
                from pathlib import Path

                await asyncio.to_thread(Path(str(image_path)).unlink, True)
            except Exception:
                pass
        # Cloudinary-hosted images are not deleted here (no public_id stored).
        return success({"deleted": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)
