"""Verification/reset code issuance and validation helpers."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import Request

from app.core import rate_limit
from app.core.auth_logic import (
    apply_wrong_entry,
    code_matches,
    latest_code_verdict,
    is_resend_in_cooldown,
)
from app.core.copy import COPY
from app.core.http import client_ip, error_response
from app.core.security import generate_code, read_valid_pass, sha256_hex
from app.db.session import query, query_one
from app.services.mailer import send_code

CodePurpose = Literal["verify", "reset"]
CODE_TTL_MS = 10 * 60 * 1000


async def issue_verification_code(purpose: CodePurpose, email: str, account_id: str | None) -> str:
    now = datetime.now(timezone.utc)
    await query(
        """
        UPDATE verification_codes
        SET voided_at = $1
        WHERE purpose = $2 AND lower(email) = lower($3)
          AND consumed_at IS NULL
          AND dead_at IS NULL
          AND voided_at IS NULL
        """,
        now,
        purpose,
        email,
    )

    code = generate_code()
    expires_at = now + timedelta(milliseconds=CODE_TTL_MS)
    await query(
        """
        INSERT INTO verification_codes (purpose, email, account_id, code_hash, expires_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        purpose,
        email,
        account_id,
        sha256_hex(code),
        expires_at,
    )
    return code


def deliver_code(purpose: CodePurpose, email: str, code: str) -> dict[str, object]:
    return send_code(purpose, email, code)


async def _load_newest_code(purpose: CodePurpose, email: str) -> dict[str, Any] | None:
    return await query_one(
        """
        SELECT * FROM verification_codes
        WHERE purpose = $1 AND lower(email) = lower($2)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        purpose,
        email,
    )


async def run_code_check(purpose: CodePurpose, request: Request, submitted_code: str) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    ip = client_ip(request)
    if not rate_limit.hit("code-check:ip", ip, *rate_limit.RateRules.code_check_ip, now_ms=now_ms):
        return {"ok": False, "response": error_response("rate_limited", COPY["TOO_MANY_ATTEMPTS"], 429)}

    pass_data = await read_valid_pass(request, purpose)
    if not pass_data:
        return {"ok": False, "response": error_response("unauthorized", COPY["UNAUTHORIZED_GENERIC"], 401)}

    claims = pass_data["claims"]
    pass_row = pass_data["row"]
    jti = claims.jti

    if not rate_limit.hit("code-check:pass", jti, *rate_limit.RateRules.code_check_pass, now_ms=now_ms):
        return {"ok": False, "response": error_response("rate_limited", COPY["TOO_MANY_ATTEMPTS"], 429)}

    row = await _load_newest_code(purpose, claims.email)
    if latest_code_verdict(row) != "open":
        return {"ok": False, "response": error_response("unauthorized", COPY["CODE_REJECTED"], 401)}

    if not code_matches(row, submitted_code):
        next_state = apply_wrong_entry(int(row.get("wrong_count") or 0), int(pass_row.get("wrong_total") or 0))
        now = datetime.now(timezone.utc)
        await query(
            """
            UPDATE verification_codes
            SET wrong_count = $1, dead_at = COALESCE($2, dead_at)
            WHERE id = $3
            """,
            next_state.next_code_wrong_count,
            now if next_state.code_now_dead else None,
            row["id"],
        )
        await query(
            """
            UPDATE pass_states
            SET wrong_total = $1, dead_at = COALESCE($2, dead_at)
            WHERE jti = $3
            """,
            next_state.next_pass_wrong_total,
            now if next_state.pass_now_dead else None,
            jti,
        )
        return {"ok": False, "response": error_response("unauthorized", COPY["CODE_REJECTED"], 401)}

    return {"ok": True, "email": claims.email, "jti": jti, "row": row}


async def can_resend_for_pass(purpose: CodePurpose, pass_data: dict[str, Any]) -> tuple[bool, Any]:
    claims = pass_data["claims"]
    pass_row = pass_data["row"]
    now_ms = int(time.time() * 1000)

    if not rate_limit.hit("resend:pass", claims.jti, *rate_limit.RateRules.resend_pass, now_ms=now_ms):
        return False, error_response("rate_limited", COPY["TOO_MANY_ATTEMPTS"], 429)

    if int(pass_row.get("wrong_total") or 0) >= 10 or pass_row.get("dead_at") is not None:
        await query(
            "UPDATE pass_states SET dead_at = $1 WHERE jti = $2",
            datetime.now(timezone.utc),
            claims.jti,
        )
        return False, error_response("unauthorized", COPY["UNAUTHORIZED_GENERIC"], 401)

    newest = await query_one(
        """
        SELECT created_at FROM verification_codes
        WHERE purpose = $1 AND lower(email) = lower($2) AND voided_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        purpose,
        claims.email,
    )
    newest_created = newest.get("created_at") if newest else None
    if is_resend_in_cooldown(newest_created, now_ms=now_ms):
        return False, error_response("rate_limited", COPY["TOO_MANY_ATTEMPTS"], 429)

    return True, None
