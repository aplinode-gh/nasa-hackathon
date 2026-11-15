"""Authentication API routes."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Request, Response

from app.core import rate_limit
from app.core.copy import COPY
from app.core.http import client_ip, error_response, success
from app.core.security import (
    clear_pass_cookies,
    mint_pass,
    read_valid_pass,
    set_pass_cookie,
)
from app.db.session import query, query_one
from app.models.auth import (
    CodeRequest,
    ForgotRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from app.services.auth_codes import can_resend_for_pass, deliver_code, issue_verification_code, run_code_check

router = APIRouter(prefix="/auth", tags=["auth"])

DUMMY_HASH = "$2b$10$gEVyLdwve7Sp00tYKm9tzueaS6qTARdH0tMp2ZV1kVtC/1ZOvEQOS"


def _now_ms() -> int:
    return int(time.time() * 1000)


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    try:
        ip = client_ip(request)
        email = payload.email.strip().lower()
        if not rate_limit.hit("login:ip", ip, *rate_limit.RateRules.login_ip, now_ms=_now_ms()) or not rate_limit.hit(
            "login:email", email, *rate_limit.RateRules.login_email, now_ms=_now_ms()
        ):
            return error_response("rate_limited", COPY["TOO_MANY_ATTEMPTS"], 429)

        user = await query_one("SELECT * FROM users WHERE lower(email) = lower($1)", email)
        password_hash = (user or {}).get("password_hash") or DUMMY_HASH
        try:
            password_matches = bcrypt.checkpw(payload.password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            password_matches = False

        if not user or not password_matches:
            return error_response("unauthorized", COPY["INVALID_CREDENTIALS"], 401)

        if not user.get("email_verified"):
            clear_pass_cookies(response, "reset")
            code = await issue_verification_code("verify", email, str(user["id"]))
            pass_data = await mint_pass("verify", account_id=str(user["id"]), email=email)
            set_pass_cookie(response, "verify", pass_data["token"])
            deliver_code("verify", email, code)
            return success({"redirect": "/verify"})

        pass_data = await mint_pass("session", account_id=str(user["id"]), email=email)
        set_pass_cookie(response, "session", pass_data["token"])
        clear_pass_cookies(response, "verify", "reset")
        return success({"redirect": "/dashboard"})
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.post("/logout")
async def logout(request: Request, response: Response):
    try:
        pass_data = await read_valid_pass(request, "session")
        if not pass_data:
            return error_response("unauthorized", COPY["UNAUTHORIZED_GENERIC"], 401)
        await query(
            "UPDATE sessions SET revoked_at = $1 WHERE id = $2 AND revoked_at IS NULL",
            datetime.now(timezone.utc),
            pass_data["claims"].jti,
        )
        clear_pass_cookies(response, "session")
        return success({"ok": True})
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.post("/signup")
async def signup(payload: SignupRequest, request: Request, response: Response):
    try:
        ip = client_ip(request)
        email = payload.email.strip().lower()
        name = payload.name.strip()
        if not rate_limit.hit("signup:ip", ip, *rate_limit.RateRules.signup_ip, now_ms=_now_ms()) or not rate_limit.hit(
            "signup:email", email, *rate_limit.RateRules.signup_email, now_ms=_now_ms()
        ):
            return error_response("rate_limited", COPY["TOO_MANY_ATTEMPTS"], 429)

        account = await query_one("SELECT * FROM users WHERE lower(email) = lower($1)", email)
        if account and account.get("email_verified"):
            return error_response("conflict_registered", COPY["EMAIL_ALREADY_REGISTERED"], 409)

        if not account:
            password_hash = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")
            try:
                account = await query_one(
                    """
                    INSERT INTO users (email, full_name, password_hash)
                    VALUES (lower($1), $2, $3)
                    RETURNING *
                    """,
                    email,
                    name,
                    password_hash,
                )
            except Exception as insert_error:
                msg = str(insert_error)
                if "duplicate key value violates unique constraint" in msg:
                    account = await query_one("SELECT * FROM users WHERE lower(email) = lower($1)", email)
                else:
                    raise

        if not account:
            return error_response("server_error", COPY["SERVER_ERROR"], 500)

        code = await issue_verification_code("verify", email, str(account["id"]))
        pass_data = await mint_pass("verify", account_id=str(account["id"]), email=email)
        set_pass_cookie(response, "verify", pass_data["token"])
        delivery = deliver_code("verify", email, code)
        payload_out = {"ok": True}
        if delivery.get("demoCode"):
            payload_out["demoCode"] = delivery["demoCode"]
        return success(payload_out)
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.post("/signup/resend")
async def signup_resend(request: Request):
    try:
        pass_data = await read_valid_pass(request, "verify")
        if not pass_data:
            return error_response("unauthorized", COPY["UNAUTHORIZED_GENERIC"], 401)

        allowed, err = await can_resend_for_pass("verify", pass_data)
        if not allowed:
            return err

        account = await query_one("SELECT id FROM users WHERE lower(email) = lower($1)", pass_data["claims"].email)
        if not account:
            return success({"ok": True})

        code = await issue_verification_code("verify", pass_data["claims"].email, str(account["id"]))
        delivery = deliver_code("verify", pass_data["claims"].email, code)
        payload_out = {"ok": True}
        if delivery.get("demoCode"):
            payload_out["demoCode"] = delivery["demoCode"]
        return success(payload_out)
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.post("/signup/verify")
async def signup_verify(payload: CodeRequest, request: Request, response: Response):
    try:
        result = await run_code_check("verify", request, payload.code)
        if not result.get("ok"):
            return result["response"]

        now = datetime.now(timezone.utc)
        await query(
            "UPDATE verification_codes SET consumed_at = $1 WHERE id = $2 AND consumed_at IS NULL",
            now,
            result["row"]["id"],
        )
        account = await query_one("SELECT id FROM users WHERE lower(email) = lower($1)", result["email"])
        if not account:
            return error_response("unauthorized", COPY["CODE_REJECTED"], 401)

        await query("UPDATE users SET email_verified = true, updated_at = $1 WHERE id = $2", now, account["id"])
        await query(
            "UPDATE pass_states SET consumed_at = $1 WHERE jti = $2 AND consumed_at IS NULL",
            now,
            result["jti"],
        )
        clear_pass_cookies(response, "verify")
        return success({"ok": True})
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.post("/forgot-password")
async def forgot_password(payload: ForgotRequest, request: Request, response: Response):
    try:
        ip = client_ip(request)
        email = payload.email.strip().lower()
        if not rate_limit.hit("forgot:ip", ip, *rate_limit.RateRules.forgot_ip, now_ms=_now_ms()) or not rate_limit.hit(
            "forgot:email", email, *rate_limit.RateRules.forgot_email, now_ms=_now_ms()
        ):
            return error_response("rate_limited", COPY["TOO_MANY_ATTEMPTS"], 429)

        pass_data = await mint_pass("reset", account_id=None, email=email)
        set_pass_cookie(response, "reset", pass_data["token"])

        account = await query_one("SELECT id FROM users WHERE lower(email) = lower($1)", email)
        if account:
            code = await issue_verification_code("reset", email, str(account["id"]))
            deliver_code("reset", email, code)

        return success({"ok": True})
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.post("/reset/resend")
async def reset_resend(request: Request):
    try:
        pass_data = await read_valid_pass(request, "reset")
        if not pass_data:
            return error_response("unauthorized", COPY["UNAUTHORIZED_GENERIC"], 401)

        allowed, err = await can_resend_for_pass("reset", pass_data)
        if not allowed:
            return err

        account = await query_one("SELECT id FROM users WHERE lower(email) = lower($1)", pass_data["claims"].email)
        if not account:
            return success({"ok": True})

        code = await issue_verification_code("reset", pass_data["claims"].email, str(account["id"]))
        delivery = deliver_code("reset", pass_data["claims"].email, code)
        payload_out = {"ok": True}
        if delivery.get("demoCode"):
            payload_out["demoCode"] = delivery["demoCode"]
        return success(payload_out)
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.post("/reset/verify")
async def reset_verify(payload: CodeRequest, request: Request):
    try:
        result = await run_code_check("reset", request, payload.code)
        if not result.get("ok"):
            return result["response"]

        await query(
            "UPDATE verification_codes SET consumed_at = $1 WHERE id = $2 AND consumed_at IS NULL",
            datetime.now(timezone.utc),
            result["row"]["id"],
        )
        account = await query_one("SELECT id FROM users WHERE lower(email) = lower($1)", result["email"])
        if not account:
            return error_response("unauthorized", COPY["CODE_REJECTED"], 401)

        await query(
            "UPDATE pass_states SET account_id = $1, stage = $2 WHERE jti = $3",
            account["id"],
            "code_verified",
            result["jti"],
        )
        return success({"ok": True})
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.post("/reset/password")
async def reset_password(payload: ResetPasswordRequest, request: Request, response: Response):
    try:
        pass_data = await read_valid_pass(request, "reset")
        if not pass_data or pass_data["row"].get("stage") != "code_verified" or not pass_data["row"].get("account_id"):
            return error_response("unauthorized", COPY["UNAUTHORIZED_GENERIC"], 401)

        account_id = pass_data["row"]["account_id"]
        email = pass_data["claims"].email
        now = datetime.now(timezone.utc)
        password_hash = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")

        await query(
            "UPDATE users SET password_hash = $1, email_verified = true, updated_at = $2 WHERE id = $3",
            password_hash,
            now,
            account_id,
        )
        await query(
            """
            UPDATE verification_codes
            SET voided_at = $1
            WHERE purpose = $2 AND lower(email) = lower($3)
              AND voided_at IS NULL
              AND consumed_at IS NULL
            """,
            now,
            "reset",
            email,
        )
        await query(
            "UPDATE pass_states SET consumed_at = $1 WHERE jti = $2 AND consumed_at IS NULL",
            now,
            pass_data["claims"].jti,
        )
        await query("DELETE FROM sessions WHERE account_id = $1", account_id)
        clear_pass_cookies(response, "reset", "verify")
        return success({"ok": True})
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.get("/session")
async def session(request: Request):
    try:
        pass_data = await read_valid_pass(request, "session")
        if not pass_data:
            return error_response("unauthorized", COPY["UNAUTHORIZED_GENERIC"], 401)

        claims = pass_data["claims"]
        user = await query_one(
            "SELECT id, email, full_name, email_verified, created_at FROM users WHERE id = $1",
            claims.sub,
        )
        if not user:
            return error_response("unauthorized", COPY["UNAUTHORIZED_GENERIC"], 401)

        return success(
            {
                "session": {
                    "accountId": str(user.get("id") or claims.sub),
                    "email": user.get("email") or claims.email,
                    "fullName": user.get("full_name"),
                    "emailVerified": bool(user.get("email_verified")),
                }
            }
        )
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)


@router.get("/pass/{kind}")
async def pass_status(kind: str, request: Request):
    """Return validity and minimal state for verify/reset passes (for SSR guards)."""
    try:
        if kind not in ("verify", "reset"):
            return error_response("validation_error", "Invalid pass kind", 422)
        pass_data = await read_valid_pass(request, kind)  # type: ignore[arg-type]
        if not pass_data:
            return success({"valid": False})
        claims = pass_data["claims"]
        row = pass_data["row"]
        return success(
            {
                "valid": True,
                "kind": kind,
                "claims": {
                    "sub": getattr(claims, "sub", None),
                    "email": getattr(claims, "email", None),
                    "typ": getattr(claims, "typ", kind),
                    "jti": getattr(claims, "jti", None),
                },
                "row": {
                    "stage": row.get("stage"),
                    "account_id": str(row.get("account_id")) if row.get("account_id") else None,
                    "email": row.get("email"),
                },
            }
        )
    except Exception:
        return error_response("server_error", COPY["SERVER_ERROR"], 500)
