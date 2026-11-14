"""Shared HTTP helpers for consistent API responses."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.serialization import to_jsonable


async def read_json_body(request: Request) -> Any:
    """Safely read JSON request body, returning None on malformed/empty input."""
    try:
        return await request.json()
    except Exception:
        return None


def success(data: Any = None, status_code: int = 200, **extra: Any) -> JSONResponse:
    """Return a JSON response payload with JSON-safe conversion."""
    if data is None and extra:
        return JSONResponse(content=to_jsonable(extra), status_code=status_code)
    if isinstance(data, dict):
        payload = {**data, **extra} if extra else data
        return JSONResponse(content=to_jsonable(payload), status_code=status_code)
    if extra:
        return JSONResponse(content=to_jsonable({"data": data, **extra}), status_code=status_code)
    return JSONResponse(content=to_jsonable(data), status_code=status_code)


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    """Return a standard error response shape."""
    return JSONResponse(content={"error": {"code": code, "message": message}}, status_code=status_code)


def client_ip(request: Request) -> str:
    """Best-effort client IP extraction for rate-limiting and logging."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "local"
