"""Helpers to convert database values into JSON-safe payloads."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def to_jsonable(value: Any) -> Any:
    """Recursively convert common DB/Python types to JSON-safe values."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        # Preserve integers as ints where possible, else float-like number.
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    # asyncpg may return JSON/JSONB as str in some configs; try parsing objects/arrays.
    if hasattr(value, "items"):
        try:
            return {str(k): to_jsonable(v) for k, v in dict(value).items()}
        except Exception:
            pass
    return str(value)


def parse_json_field(value: Any, default: Any):
    """Parse JSON text fields when needed."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return value
