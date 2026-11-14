"""Authentication pass/token helpers."""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import Request, Response
from jose import JWTError, jwt

from app.core.config import settings
from app.db.session import query, query_one

PassKind = Literal["verify", "reset", "session"]

PASS_COOKIE_NAMES: dict[PassKind, str] = {
    "verify": "agro_verify",
    "reset": "agro_reset",
    "session": "agro_session",
}

PASS_TTL_SECONDS: dict[PassKind, int] = {
    "verify": 60 * 60,
    "reset": 60 * 60,
    "session": 7 * 24 * 60 * 60,
}


@dataclass
class PassClaims:
    sub: str
    email: str
    typ: PassKind
    jti: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _signing_key() -> str:
    secret = settings.jwt_secret or ""
    if len(secret) < 16:
        raise RuntimeError("JWT_SECRET is missing or too short (min 16 chars)")
    return secret


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def decode_pass_token(token: str, kind: PassKind) -> PassClaims | None:
    try:
        payload = jwt.decode(token, _signing_key(), algorithms=["HS256"])
        sub = payload.get("sub")
        jti = payload.get("jti")
        typ = payload.get("typ")
        email = payload.get("email")
        if not sub or not jti or typ != kind or not isinstance(email, str):
            return None
        return PassClaims(sub=str(sub), email=email, typ=kind, jti=str(jti))
    except JWTError:
        return None


def sign_pass_token(claims: PassClaims, ttl_seconds: int) -> str:
    now = _utc_now()
    payload = {
        "sub": claims.sub,
        "jti": claims.jti,
        "typ": claims.typ,
        "email": claims.email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, _signing_key(), algorithm="HS256")


async def mint_pass(kind: PassKind, *, account_id: str | None, email: str) -> dict[str, Any]:
    jti = str(uuid.uuid4())
    expires_at = _utc_now() + timedelta(seconds=PASS_TTL_SECONDS[kind])
    token = sign_pass_token(
        PassClaims(
            sub=email if kind == "reset" else (account_id or ""),
            email=email,
            typ=kind,
            jti=jti,
        ),
        PASS_TTL_SECONDS[kind],
    )

    if kind == "session":
        if not account_id:
            raise ValueError("Session pass requires an account id")
        await query(
            "INSERT INTO sessions (id, account_id, expires_at) VALUES ($1, $2, $3)",
            jti,
            account_id,
            expires_at,
        )
    else:
        await query(
            "INSERT INTO pass_states (jti, kind, email, account_id, expires_at) VALUES ($1, $2, $3, $4, $5)",
            jti,
            kind,
            email,
            account_id,
            expires_at,
        )

    return {"token": token, "jti": jti, "expires_at": expires_at}


def set_pass_cookie(response: Response, kind: PassKind, token: str) -> None:
    secure = os.getenv("NODE_ENV") == "production"
    response.set_cookie(
        key=PASS_COOKIE_NAMES[kind],
        value=token,
        max_age=PASS_TTL_SECONDS[kind],
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_pass_cookies(response: Response, *kinds: PassKind) -> None:
    for kind in kinds:
        response.delete_cookie(
            key=PASS_COOKIE_NAMES[kind],
            path="/",
            httponly=True,
            samesite="lax",
        )


async def _load_live_pass_state_row(claims: PassClaims) -> dict[str, Any] | None:
    row = await query_one("SELECT * FROM pass_states WHERE jti = $1", claims.jti)
    if not row or row.get("kind") != claims.typ:
        return None
    if row.get("consumed_at") is not None or row.get("dead_at") is not None:
        return None
    expires_at = row.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at <= _utc_now():
        return None
    if row.get("email") != claims.email:
        return None
    if row.get("account_id"):
        account = await query_one("SELECT id FROM users WHERE id = $1", row["account_id"])
        if not account:
            return None
    return row


async def _load_live_session_row(claims: PassClaims) -> dict[str, Any] | None:
    row = await query_one("SELECT * FROM sessions WHERE id = $1", claims.jti)
    if not row:
        return None
    if row.get("revoked_at") is not None:
        return None
    expires_at = row.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at <= _utc_now():
        return None
    account = await query_one("SELECT id FROM users WHERE id = $1", row.get("account_id"))
    if not account:
        return None
    return row


async def read_valid_pass(request: Request, kind: PassKind) -> dict[str, Any] | None:
    token = request.cookies.get(PASS_COOKIE_NAMES[kind])
    if not token:
        return None
    claims = decode_pass_token(token, kind)
    if not claims:
        return None
    if kind == "session":
        row = await _load_live_session_row(claims)
        if not row:
            return None
        return {"kind": kind, "claims": claims, "row": row}
    row = await _load_live_pass_state_row(claims)
    if not row:
        return None
    return {"kind": kind, "claims": claims, "row": row}


async def require_session(request: Request) -> dict[str, str] | None:
    pass_data = await read_valid_pass(request, "session")
    if not pass_data:
        return None
    claims: PassClaims = pass_data["claims"]
    return {"accountId": claims.sub, "email": claims.email}
