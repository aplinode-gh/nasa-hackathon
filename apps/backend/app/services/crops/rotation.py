"""Crop rotation suggestion helpers."""

from __future__ import annotations

from typing import Any

from app.db.session import query
from app.services.crops.common import SEASON_ORDER


def _advance_season(season: str, steps: int) -> tuple[str, int]:
    idx = SEASON_ORDER.index(season) if season in SEASON_ORDER else 0
    total = idx + steps
    return SEASON_ORDER[total % len(SEASON_ORDER)], total // len(SEASON_ORDER)


async def build_rotation(
    saved_crop: dict[str, Any],
    target_season: str,
    target_year: int,
    has_history: bool,
    all_crops: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a short rotation plan from saved crop and historical context."""
    rules = await query(
        """
        SELECT next_crop_id, benefit, reason_key, suitability_score
        FROM crop_rotation_rules
        WHERE previous_crop_id = $1
        ORDER BY suitability_score DESC
        LIMIT 3
        """,
        saved_crop["id"],
    )
    crop_by_id = {crop["id"]: crop for crop in all_crops}
    suggestions: list[dict[str, Any]] = []

    for index, rule in enumerate((rules or [])[:3], start=1):
        next_crop = crop_by_id.get(rule.get("next_crop_id"), saved_crop)
        next_season, years = _advance_season(target_season, index)
        suggestions.append(
            {
                "sequencePosition": index,
                "targetSeason": next_season,
                "targetYear": target_year + years,
                "crop": next_crop,
                "reasonKey": rule.get("reason_key") or "app.crops.rotation.generic",
                "isGeneric": not has_history,
            }
        )

    if not suggestions:
        next_season, years = _advance_season(target_season, 1)
        suggestions.append(
            {
                "sequencePosition": 1,
                "targetSeason": next_season,
                "targetYear": target_year + years,
                "crop": saved_crop,
                "reasonKey": "app.crops.rotation.generic",
                "isGeneric": True,
            }
        )
    return suggestions
