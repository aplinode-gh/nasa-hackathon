"""Pest risk forecasting from weather and crop growth stage."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from app.core.serialization import parse_json_field
from app.services.weather.service import get_forecast

PEST_BY_CROP: dict[str, list[dict[str, Any]]] = {
    "cotton": [
        {"name": "Whitefly", "temp_min": 28, "temp_max": 40, "humidity_max": 65},
        {"name": "Bollworm", "temp_min": 20, "temp_max": 35, "humidity_min": 55},
        {"name": "Jassid", "temp_min": 25, "temp_max": 38, "humidity_min": 50},
    ],
    "wheat": [
        {"name": "Aphid", "temp_min": 12, "temp_max": 25, "humidity_min": 55},
        {"name": "Rust", "temp_min": 15, "temp_max": 28, "humidity_min": 70},
    ],
    "rice": [
        {"name": "Armyworm", "temp_min": 22, "temp_max": 34, "humidity_min": 60},
        {"name": "Stem borer", "temp_min": 24, "temp_max": 35, "humidity_min": 65},
    ],
    "maize": [
        {"name": "Armyworm", "temp_min": 20, "temp_max": 34, "humidity_min": 50},
        {"name": "Aphid", "temp_min": 15, "temp_max": 27, "humidity_min": 55},
    ],
    "sugarcane": [
        {"name": "Borers", "temp_min": 22, "temp_max": 36, "humidity_min": 55},
        {"name": "Pyrilla", "temp_min": 24, "temp_max": 35, "humidity_min": 60},
    ],
    "mustard": [{"name": "Aphid", "temp_min": 10, "temp_max": 24, "humidity_min": 50}],
    "potato": [{"name": "Late blight", "temp_min": 12, "temp_max": 24, "humidity_min": 70}],
    "tomato": [{"name": "Whitefly", "temp_min": 22, "temp_max": 35, "humidity_min": 45}],
    "onion": [{"name": "Thrips", "temp_min": 22, "temp_max": 36, "humidity_max": 60}],
}

DEFAULT_PESTS = [
    {"name": "Aphid", "temp_min": 15, "temp_max": 30, "humidity_min": 50},
    {"name": "Armyworm", "temp_min": 22, "temp_max": 35, "humidity_min": 55},
]

RECOMMENDATIONS = {
    "Whitefly": "Scout the underside of leaves and consider yellow sticky traps; treat when populations rise.",
    "Bollworm": "Inspect squares and bolls; apply a recommended biorational or chemical control at threshold.",
    "Jassid": "Monitor leaf curling and use a recommended control if damage spreads.",
    "Aphid": "Check new growth; encourage natural enemies and treat hot spots early.",
    "Rust": "Look for orange pustules and apply a recommended fungicide if infection is spreading.",
    "Armyworm": "Scout whorls and field edges; treat young larvae before they cause heavy defoliation.",
    "Stem borer": "Inspect stems for dead hearts and apply recommended control at early infestation.",
    "Borers": "Check internodes and apply recommended control where damage is found.",
    "Pyrilla": "Monitor colonies on leaves and treat when honeydew and sooty mould appear.",
    "Late blight": "Improve airflow, avoid overhead irrigation, and apply a recommended fungicide.",
    "Thrips": "Check leaf silvering and use recommended control when damage reaches threshold.",
}


def _day_label(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def _demo_days(crop: str) -> list[dict[str, Any]]:
    base = 30 + (sum(ord(c) for c in crop) % 8)
    days = []
    for i in range(7):
        days.append(
            {
                "date": _day_label(i),
                "temp_max": base + 2 + ((i * 3) % 7),
                "temp_min": base - 10 + (i % 4),
                "precip_mm": round(((i * 7) % 14) * 0.8, 1),
                "humidity": 55 + ((i * 11) % 35),
                "description": "Partly cloudy",
                "condition": "Clouds",
            }
        )
    return days


def _growth_stage(growth_stages: Any, crop: str) -> str:
    stages = parse_json_field(growth_stages, {})
    if isinstance(stages, dict):
        return str(stages.get(crop) or next(iter(stages.values()), "Sowing"))
    return "Sowing"


def _crop_pests(crop: str) -> list[dict[str, Any]]:
    return PEST_BY_CROP.get((crop or "").lower(), DEFAULT_PESTS)


def _match_pest(crop: str, day: dict[str, Any]) -> dict[str, Any] | None:
    temp = float(day.get("temp_max") or 0)
    humidity = float(day.get("humidity") or 0)
    for pest in _crop_pests(crop):
        if temp < float(pest.get("temp_min", 0)) or temp > float(pest.get("temp_max", 99)):
            continue
        if "humidity_min" in pest and humidity < float(pest["humidity_min"]):
            continue
        if "humidity_max" in pest and humidity > float(pest["humidity_max"]):
            continue
        return pest
    return None


def _risk_score(day: dict[str, Any], stage: str, pest: dict[str, Any] | None) -> int:
    humidity = float(day.get("humidity") or 0)
    precip = float(day.get("precip_mm") or 0)
    temp = float(day.get("temp_max") or 0)

    score = 15.0
    score += min(humidity, 100) * 0.35
    score += min(precip, 25) * 1.2
    if 20 <= temp <= 35:
        score += 10
    if pest:
        score += 22
    if stage.lower() in ("flowering", "squaring", "boll filling", "vegetative"):
        score += 8
    return max(0, min(100, int(round(score))))


def build_forecast(farm: dict[str, Any], crop: str, weather: dict[str, Any] | None) -> dict[str, Any]:
    unavailable = weather is None
    raw_days = (weather or {}).get("days") if weather else None
    days = list(raw_days or _demo_days(crop))[:7]
    stage = _growth_stage(farm.get("growth_stages"), crop)

    out_days = []
    for index, day in enumerate(days):
        pest = _match_pest(crop, day)
        score = _risk_score(day, stage, pest)
        if score < 40:
            pest = None
        confidence = max(35, min(92, 92 - index * 4 - (8 if unavailable else 0)))
        out_days.append(
            {
                "date": str(day.get("date") or _day_label(index)),
                "risk_score": score,
                "predicted_pest": pest["name"] if pest else None,
                "confidence": confidence,
                "status": "active" if score >= 70 else "monitoring",
            }
        )

    return {
        "farm_id": str(farm.get("id")),
        "farm_name": farm.get("name"),
        "crop": crop,
        "growth_stage": stage,
        "weather_data_unavailable": unavailable,
        "days": out_days,
    }


def alert_payload(farm: dict[str, Any], crop: str, day: dict[str, Any]) -> dict[str, Any] | None:
    if day["risk_score"] < 70 or not day.get("predicted_pest"):
        return None
    pest = day["predicted_pest"]
    return {
        "farm_id": farm.get("id"),
        "crop": crop,
        "pest_type": pest,
        "risk_score": int(day["risk_score"]),
        "severity": "critical" if day["risk_score"] >= 85 else "warning",
        "recommendation_text": RECOMMENDATIONS.get(pest, "Monitor the field closely and act early if damage appears."),
        "status": day["status"],
    }


def stage_merge(existing: Any, crop: str, stage: str) -> dict[str, Any]:
    stages = parse_json_field(existing, {})
    if not isinstance(stages, dict):
        stages = {}
    merged = {str(k): str(v) for k, v in stages.items()}
    merged[crop] = stage
    return merged


def stages_to_json(stages: dict[str, Any]) -> str:
    return json.dumps(stages)
