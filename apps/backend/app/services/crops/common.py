"""Shared helpers for crop recommendation features."""

from __future__ import annotations

from typing import Any

BUDGET_CAP = {
    "low": 25000,
    "medium": 60000,
    "high": 120000,
    "very_high": 10**12,
}

SEASON_ORDER = ["winter", "spring", "summer", "rainy", "autumn", "windy"]

SEASON_LABELS = {
    "summer": "Summer",
    "winter": "Winter",
    "autumn": "Autumn",
    "spring": "Spring",
    "rainy": "Rainy",
    "windy": "Windy",
}

SOIL_LABELS = {
    "sandy": "Sandy",
    "sandy_loam": "Sandy loam",
    "loamy": "Loamy",
    "clay_loam": "Clay loam",
    "clay": "Clay",
    "silty": "Silty",
    "saline": "Saline",
    "rocky": "Rocky",
    "other": "Not sure / Other",
}

NATIONAL_DEFAULT_SOIL = "loamy"


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def map_crop_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a crop row into API-friendly camelCase fields."""
    season_windows = row.get("season_windows") or []
    if isinstance(season_windows, str):
        season_windows = [season_windows]
    return {
        "id": row.get("id"),
        "nameEn": row.get("name_en"),
        "nameKey": row.get("name_key"),
        "category": row.get("category"),
        "typicalYieldPerAcreKg": float(row.get("typical_yield_per_acre_kg") or 0),
        "growingDurationDays": int(row.get("growing_duration_days") or 0),
        "seasonWindows": season_windows,
        "waterRequirementLevel": row.get("water_requirement_level"),
        "labourCostLevel": row.get("labour_cost_level"),
        "capitalRequirementPerAcrePkr": float(row.get("capital_requirement_per_acre_pkr") or 0),
        "marketRiskBaseline": row.get("market_risk_baseline"),
    }
