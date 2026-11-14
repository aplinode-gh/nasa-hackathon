"""District proximity and distance helpers for market lookups."""

from __future__ import annotations

import math
from typing import Any

from app.db.session import query_one

EARTH_RADIUS_KM = 6371


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Compute straight-line distance between two coordinates in kilometers."""
    def to_rad(degrees: float) -> float:
        return degrees * math.pi / 180

    d_lat = to_rad(lat2 - lat1)
    d_lng = to_rad(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(d_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(EARTH_RADIUS_KM * c * 10) / 10


async def _nearest_hub() -> dict[str, Any] | None:
    return await query_one(
        """
        SELECT * FROM mandis
        WHERE is_hub = true AND province = 'punjab'
        ORDER BY CASE WHEN district = 'lahore' THEN 0 ELSE 1 END
        LIMIT 1
        """
    )


async def resolve_district_context(district_slug: str | None) -> dict[str, Any]:
    """Resolve search districts and fallback hub information for a district."""
    if not district_slug:
        hub = await _nearest_hub() or {}
        district = hub.get("district") or "lahore"
        return {
            "district": district,
            "isFallbackHub": True,
            "searchDistricts": [district],
            "farmLat": hub.get("latitude"),
            "farmLng": hub.get("longitude"),
        }

    mandi = await query_one(
        "SELECT * FROM mandis WHERE lower(district) = lower($1) LIMIT 1",
        district_slug,
    )
    if not mandi:
        hub = await _nearest_hub() or {}
        district = hub.get("district") or "lahore"
        return {
            "district": district,
            "isFallbackHub": True,
            "searchDistricts": [district],
            "farmLat": hub.get("latitude"),
            "farmLng": hub.get("longitude"),
        }

    bordering = mandi.get("bordering_districts") or []
    if not isinstance(bordering, list):
        bordering = []
    search_districts = list(dict.fromkeys([mandi.get("district"), *bordering]))
    return {
        "district": mandi.get("district"),
        "isFallbackHub": False,
        "searchDistricts": [d for d in search_districts if d],
        "farmLat": mandi.get("latitude"),
        "farmLng": mandi.get("longitude"),
    }
