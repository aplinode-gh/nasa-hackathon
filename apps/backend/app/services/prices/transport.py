"""Transport cost estimation helpers."""

from __future__ import annotations

from typing import Any

TRANSPORT_COST_PER_KM_PKR = 15


def estimate_transport_cost(distance_km: Any) -> float | None:
    """Estimate transport cost from distance in kilometers."""
    if distance_km is None:
        return None
    try:
        value = float(distance_km)
    except Exception:
        return None
    if value != value:  # NaN
        return None
    return round(value * TRANSPORT_COST_PER_KM_PKR * 100) / 100
