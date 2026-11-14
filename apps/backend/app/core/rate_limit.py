"""Simple in-memory fixed-window rate limiter."""

from __future__ import annotations

import time
from dataclasses import dataclass

MINUTE_MS = 60_000
HOUR_MS = 60 * MINUTE_MS


@dataclass
class Bucket:
    window_start: int
    count: int


_buckets: dict[str, Bucket] = {}
_MAX_KEYS = 5000


def hit(scope: str, key: str, limit: int, window_ms: int, now_ms: int | None = None) -> bool:
    """Return True if request is allowed, False if limit exceeded."""
    now = int(time.time() * 1000) if now_ms is None else now_ms
    bucket_id = f"{scope}:{key}"
    bucket = _buckets.get(bucket_id)
    if bucket is None or now - bucket.window_start >= window_ms:
        bucket = Bucket(window_start=now, count=0)
        _buckets[bucket_id] = bucket
    bucket.count += 1

    if len(_buckets) > _MAX_KEYS:
        cutoff = now - 2 * window_ms
        stale = [k for k, v in _buckets.items() if v.window_start < cutoff]
        for k in stale:
            _buckets.pop(k, None)

    return bucket.count <= limit


def reset_for_tests() -> None:
    _buckets.clear()


class RateRules:
    signup_ip = (5, HOUR_MS)
    signup_email = (5, HOUR_MS)
    login_ip = (10, 15 * MINUTE_MS)
    login_email = (8, 15 * MINUTE_MS)
    forgot_ip = (3, HOUR_MS)
    forgot_email = (3, HOUR_MS)
    resend_pass = (5, HOUR_MS)
    code_check_ip = (20, HOUR_MS)
    code_check_pass = (30, HOUR_MS)
    crops_ip = (20, HOUR_MS)
    advisor_chat_ip = (30, HOUR_MS)
    advisor_chat_account = (50, HOUR_MS)
    app_control_chat_ip = (30, HOUR_MS)
    app_control_chat_account = (50, HOUR_MS)
