"""Crop catalogue and soil-compatibility lookups."""

from __future__ import annotations

from typing import Any

from app.db.session import query, query_one
from app.services.crops.common import BUDGET_CAP, NATIONAL_DEFAULT_SOIL, map_crop_row


async def list_crops(season: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []

    if season:
        values.append([season])
        clauses.append(f"season_windows @> ${len(values)}::text[]")
    if category:
        values.append(category)
        clauses.append(f"category = ${len(values)}")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = await query(f"SELECT * FROM crops {where} ORDER BY name_en", *values)
    return [map_crop_row(r) for r in (rows or [])]


async def get_crops_by_season_and_budget(season: str, budget: str) -> list[dict[str, Any]]:
    cap = BUDGET_CAP.get(budget, BUDGET_CAP["very_high"])
    rows = await query(
        """
        SELECT * FROM crops
        WHERE season_windows @> $1::text[]
          AND capital_requirement_per_acre_pkr <= $2
        ORDER BY name_en
        """,
        [season],
        cap,
    )
    return [map_crop_row(r) for r in (rows or [])]


async def get_compatibility_by_crop(soil_type: str) -> dict[str, float]:
    rows = await query(
        "SELECT crop_id, suitability_score FROM crop_soil_compatibility WHERE soil_type = $1",
        soil_type,
    )
    out: dict[str, float] = {}
    for row in rows or []:
        try:
            out[str(row.get("crop_id"))] = float(row.get("suitability_score") or 0)
        except Exception:
            continue
    return out


async def resolve_soil_type(declared_soil: str, district: str) -> dict[str, Any]:
    """Resolve effective soil type, falling back to regional or national defaults."""
    if declared_soil != "other":
        return {"soilType": declared_soil, "isRegionalDefault": False, "note": "exact"}

    profile = await query_one(
        """
        SELECT dominant_soil_type, secondary_soil_type, province
        FROM soil_profiles
        WHERE lower(district) = lower($1)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        district or "",
    )
    if profile and profile.get("dominant_soil_type"):
        return {
            "soilType": str(profile.get("dominant_soil_type")),
            "isRegionalDefault": True,
            "note": "regional",
        }

    return {"soilType": NATIONAL_DEFAULT_SOIL, "isRegionalDefault": True, "note": "national"}
