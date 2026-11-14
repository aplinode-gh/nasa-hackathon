"""Weather snapshot helper for farm records."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx


def empty_snapshot() -> dict[str, Any]:
    return {
        "condition": None,
        "temp_c": None,
        "humidity": None,
        "wind_kph": None,
        "fetched_at": None,
    }


async def fetch_current_weather(lat: float, lng: float, date_str: str | None = None) -> dict[str, Any]:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return empty_snapshot()

    params: dict[str, Any] = {"lat": lat, "lon": lng, "appid": api_key, "units": "metric"}
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            params["dt"] = int(dt.timestamp())
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.openweathermap.org/data/2.5/weather", params=params)
        if resp.status_code != 200:
            return empty_snapshot()
        data = resp.json()
        wind_mps = (data.get("wind") or {}).get("speed")
        return {
            "condition": (data.get("weather") or [{}])[0].get("main"),
            "temp_c": (data.get("main") or {}).get("temp"),
            "humidity": (data.get("main") or {}).get("humidity"),
            "wind_kph": round(float(wind_mps) * 3.6) if wind_mps is not None else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        return empty_snapshot()
