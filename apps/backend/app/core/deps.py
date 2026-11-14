"""Authentication dependencies for protected endpoints."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.copy import COPY
from app.core.http import error_response
from app.core.security import read_valid_pass


async def require_session(request: Request) -> dict[str, str]:
    """Return authenticated account context or raise 401."""
    pass_data = await read_valid_pass(request, "session")
    if not pass_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": COPY["UNAUTHORIZED_GENERIC"]},
        )
    claims = pass_data["claims"]
    return {"accountId": str(claims.sub), "email": str(claims.email)}
