"""Favourite crop preferences API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.deps import require_session
from app.core.http import error_response, read_json_body, success
from app.core.serialization import to_jsonable
from app.db.session import execute, query, query_one

router = APIRouter(prefix="/favourites", tags=["favourites"])


class FavouriteCropRequest(BaseModel):
    crop_id: str = Field(..., min_length=1)
    display_order: int | None = Field(default=None, ge=0)


async def _list_favourites(account_id: str):
    rows = await query(
        """
        SELECT crop_id, display_order
        FROM user_crop_preferences
        WHERE user_id = $1
        ORDER BY display_order ASC
        """,
        account_id,
    )
    return to_jsonable(rows or [])


@router.get("")
async def get_favourites(session: dict = Depends(require_session)):
    try:
        return success({"favourites": await _list_favourites(session["accountId"])})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("")
async def add_favourite(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = FavouriteCropRequest.model_validate(body or {})

        crop = await query_one("SELECT id FROM crops WHERE id = $1", parsed.crop_id)
        if not crop:
            return error_response("not_found", "Crop not found", 404)

        display_order = parsed.display_order if parsed.display_order is not None else 0
        await execute(
            """
            INSERT INTO user_crop_preferences (user_id, crop_id, display_order)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, crop_id)
            DO UPDATE SET display_order = EXCLUDED.display_order
            """,
            session["accountId"],
            parsed.crop_id,
            display_order,
        )
        return success({"favourites": await _list_favourites(session["accountId"])})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "crop_id" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.delete("")
async def delete_favourite(request: Request, session: dict = Depends(require_session)):
    try:
        crop_id = request.query_params.get("crop_id")
        if not crop_id:
            return error_response("validation_error", "crop_id is required", 422)

        await execute(
            "DELETE FROM user_crop_preferences WHERE user_id = $1 AND crop_id = $2",
            session["accountId"],
            crop_id,
        )
        return success({"favourites": await _list_favourites(session["accountId"])})
    except Exception as err:
        return error_response("server_error", str(err), 500)
