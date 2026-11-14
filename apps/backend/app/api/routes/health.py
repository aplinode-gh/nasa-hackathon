"""Health check endpoint."""

from fastapi import APIRouter

from app.core.http import error_response, success
from app.db.session import query_one

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    try:
        await query_one("SELECT 1 AS ok")
        return success({"status": "ok", "database": "connected"})
    except Exception as exc:
        message = str(exc) or "Unknown error"
        return error_response("server_error", message, 500)
