"""Pure helpers for authentication code and session logic."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.security import sha256_hex

CODE_TTL_MS = 10 * 60 * 1000
CODE_MAX_WRONG = 5
PASS_MAX_WRONG_TOTAL = 10
RESEND_COOLDOWN_MS = 60 * 1000


def mask_email(email: str) -> str:
    at_index = email.find("@")
    if at_index <= 0:
        return f"•••@{email}"
    local = email[:at_index]
    domain = email[at_index:]
    return f"{local[0]}•••{domain}"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email))


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def latest_code_verdict(row: dict[str, Any] | None, now_ms: int | None = None) -> str:
    if row is None:
        return "none"
    now_dt = datetime.now(timezone.utc) if now_ms is None else datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
    if row.get("consumed_at") is not None:
        return "voided"
    if row.get("voided_at") is not None:
        return "voided"
    if row.get("dead_at") is not None:
        return "dead"
    expires_at = _parse_dt(row.get("expires_at"))
    if expires_at is None or expires_at <= now_dt:
        return "expired"
    return "open"


def code_matches(row: dict[str, Any], candidate: str) -> bool:
    return row.get("code_hash") == sha256_hex(candidate)


@dataclass
class WrongEntryOutcome:
    next_code_wrong_count: int
    code_now_dead: bool
    next_pass_wrong_total: int
    pass_now_dead: bool


def apply_wrong_entry(current_code_wrong_count: int, current_pass_wrong_total: int) -> WrongEntryOutcome:
    next_code_wrong_count = current_code_wrong_count + 1
    next_pass_wrong_total = current_pass_wrong_total + 1
    return WrongEntryOutcome(
        next_code_wrong_count=next_code_wrong_count,
        code_now_dead=next_code_wrong_count >= CODE_MAX_WRONG,
        next_pass_wrong_total=next_pass_wrong_total,
        pass_now_dead=next_pass_wrong_total >= PASS_MAX_WRONG_TOTAL,
    )


def is_resend_in_cooldown(newest_code_created_at: Any, now_ms: int | None = None) -> bool:
    created = _parse_dt(newest_code_created_at)
    if created is None:
        return False
    now_dt = datetime.now(timezone.utc) if now_ms is None else datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
    return (now_dt - created).total_seconds() * 1000 < RESEND_COOLDOWN_MS
