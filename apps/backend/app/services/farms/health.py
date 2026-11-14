"""Farm health heuristics."""

from __future__ import annotations

from typing import Any


def compute_farm_health(growth_stages: dict[str, str] | None, recent_records: list[dict[str, Any]]) -> str:
    record_types = [r.get("type") for r in (recent_records or [])]
    has_irrigation = any(t in ("irrigation", "fertilizer", "pesticide") for t in record_types)
    has_harvest = any(t == "harvest" for t in record_types)
    has_disease = any(t == "disease" for t in record_types)
    if has_disease:
        return "watch"
    if not has_irrigation and not has_harvest and len(recent_records or []) == 0:
        return "watch"
    return "good"
