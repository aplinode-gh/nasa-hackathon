"""CACP projected-cost client with a local fallback table."""

from __future__ import annotations

import os
from typing import Any

import httpx

CATEGORIES = ["seed", "fertilizer", "labor", "irrigation", "transport"]

FALLBACK_PROJECTIONS: dict[str, dict[str, float]] = {
    "wheat": {"seed": 1200, "fertilizer": 3500, "labor": 4500, "irrigation": 1800, "transport": 800},
    "cotton": {"seed": 2500, "fertilizer": 6000, "labor": 5500, "irrigation": 3500, "transport": 1500},
    "sugarcane": {"seed": 3500, "fertilizer": 8000, "labor": 7000, "irrigation": 4000, "transport": 2000},
    "maize": {"seed": 1000, "fertilizer": 3000, "labor": 3500, "irrigation": 1500, "transport": 700},
    "rice": {"seed": 1500, "fertilizer": 4500, "labor": 5000, "irrigation": 2500, "transport": 1200},
}


def _rows(costs: dict[str, float], acres: float) -> list[dict[str, Any]]:
    return [
        {
            "category": category,
            "per_acre_cost_pkr": float(costs.get(category) or 0),
            "total_projected_pkr": round(float(costs.get(category) or 0) * acres, 2),
        }
        for category in CATEGORIES
    ]


async def fetch_cacp_projections(crop_id: str, acres: float) -> list[dict[str, Any]] | None:
    """Fetch per-acre projections from CACP, falling back to local baselines."""
    base_url = os.getenv("CACP_API_URL")
    if base_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(base_url, params={"crop": crop_id})
                response.raise_for_status()
                costs = (response.json() or {}).get("costs")
                if isinstance(costs, dict):
                    return _rows(costs, acres)
        except Exception:
            pass

    fallback = FALLBACK_PROJECTIONS.get((crop_id or "").lower())
    if not fallback:
        return None
    return _rows(fallback, acres)
