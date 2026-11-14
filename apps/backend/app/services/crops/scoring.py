"""Scoring and ranking helpers for crop recommendations."""

from __future__ import annotations

from typing import Any

from app.services.crops.common import clamp01

WEIGHTS = {
    "suitability": 0.3,
    "weather": 0.2,
    "profit": 0.25,
    "risk": 0.15,
    "sustain": 0.1,
}
RISK_BASE = {"low": 0.2, "medium": 0.5, "high": 0.8}
WATER_SCORE = {"low": 1.0, "medium": 0.7, "high": 0.4}
MAAN_KG = 40


def _revenue_per_acre(crop: dict[str, Any], price_per_maan_pkr: float) -> int:
    price_per_kg = price_per_maan_pkr / MAAN_KG
    return round(float(crop.get("typicalYieldPerAcreKg") or 0) * price_per_kg)


def _suitability_score(crop: dict[str, Any], ctx: dict[str, Any]) -> float:
    base = float((ctx.get("compatibilityByCrop") or {}).get(crop["id"], 0.6))
    score = base
    if crop.get("waterRequirementLevel") == "high" and ctx.get("irrigation") == "rainfed":
        score -= 0.25
    if crop.get("waterRequirementLevel") == "low" and ctx.get("irrigation") == "canal":
        score += 0.02
    return clamp01(score)


def _weather_fit_score(crop: dict[str, Any], ctx: dict[str, Any]) -> float:
    if not ctx.get("weatherAvailable"):
        return 0.65
    season = ctx.get("season")
    category = crop.get("category")
    season_fit = {
        "summer": 0.8 if category == "vegetable" else 0.72,
        "winter": 0.82 if category == "staple" else 0.7,
        "autumn": 0.74,
        "spring": 0.76,
        "rainy": 0.85 if crop.get("waterRequirementLevel") == "high" else 0.68,
        "windy": 0.7,
    }
    return clamp01(float(season_fit.get(season, 0.72)))


def _profitability_score(crop: dict[str, Any], ctx: dict[str, Any]) -> float:
    if not ctx.get("marketAvailable"):
        return 0.6
    price = (ctx.get("priceByCrop") or {}).get(crop["id"])
    if not price:
        return 0.55
    revenue = _revenue_per_acre(crop, float(price.get("pricePerMaanPkr") or 0))
    capital = float(crop.get("capitalRequirementPerAcrePkr") or 0)
    margin_share = (revenue - capital) / (revenue + 1)
    score = clamp01(0.5 + margin_share)
    trend = price.get("trend")
    if trend == "up":
        score += 0.1
    elif trend == "down":
        score -= 0.1
    return clamp01(score)


def _risk_score(crop: dict[str, Any], ctx: dict[str, Any]) -> float:
    base = RISK_BASE.get(crop.get("marketRiskBaseline"), 0.5)
    price = (ctx.get("priceByCrop") or {}).get(crop["id"]) or {}
    volatility = float(price.get("volatility") or 0.15)
    return clamp01(base + volatility * 0.3)


def _sustainability_score(crop: dict[str, Any], ctx: dict[str, Any]) -> float:
    nitrogen = 1.0 if crop.get("category") == "pulse" else 0.5
    water = WATER_SCORE.get(crop.get("waterRequirementLevel"), 0.7)
    last_category = ctx.get("lastCropCategory")
    rotation_fit = 0.9 if last_category and last_category != crop.get("category") else 0.6
    return clamp01(0.5 * nitrogen + 0.3 * water + 0.2 * rotation_fit)


def score_crop(crop: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    suitability = _suitability_score(crop, ctx)
    weather_fit = _weather_fit_score(crop, ctx)
    profitability = _profitability_score(crop, ctx)
    risk = _risk_score(crop, ctx)
    sustainability = _sustainability_score(crop, ctx)

    weight_sum = 0.0
    weighted = 0.0
    weight_sum += WEIGHTS["suitability"]
    weighted += WEIGHTS["suitability"] * suitability
    if ctx.get("weatherAvailable"):
        weight_sum += WEIGHTS["weather"]
        weighted += WEIGHTS["weather"] * weather_fit
    if ctx.get("marketAvailable"):
        weight_sum += WEIGHTS["profit"]
        weighted += WEIGHTS["profit"] * profitability
    weight_sum += WEIGHTS["risk"]
    weighted += WEIGHTS["risk"] * (1 - risk)
    weight_sum += WEIGHTS["sustain"]
    weighted += WEIGHTS["sustain"] * sustainability
    final_score = clamp01(weighted / weight_sum if weight_sum else 0.0)

    price = (ctx.get("priceByCrop") or {}).get(crop["id"])
    expected_revenue = (
        _revenue_per_acre(crop, float(price.get("pricePerMaanPkr") or 0))
        if ctx.get("marketAvailable") and price
        else 0
    )

    risk_factors: list[str] = []
    if crop.get("marketRiskBaseline") == "high" or (price and float(price.get("volatility") or 0) > 0.3):
        risk_factors.append("price_volatility")
    if crop.get("category") == "vegetable":
        risk_factors.append("pest_pressure")
    if crop.get("waterRequirementLevel") == "high" and ctx.get("irrigation") == "rainfed":
        risk_factors.append("water_stress")
    if not ctx.get("weatherAvailable"):
        risk_factors.append("weather")
    if float(crop.get("capitalRequirementPerAcrePkr") or 0) > 60000:
        risk_factors.append("input_cost")

    if not ctx.get("marketAvailable"):
        revenue_confidence = "unreliable"
    elif price and float(price.get("volatility") or 0) > 0.4:
        revenue_confidence = "low"
    elif price and float(price.get("volatility") or 0) > 0.15:
        revenue_confidence = "medium"
    else:
        revenue_confidence = "high"

    data_sources: list[str] = []
    if ctx.get("weatherAvailable"):
        data_sources.append("weather")
    if ctx.get("marketAvailable"):
        data_sources.append("market")
    data_sources.append("soil")

    return {
        "crop": crop,
        "scores": {
            "suitability": suitability,
            "weatherFit": weather_fit,
            "profitability": profitability,
            "risk": risk,
            "sustainability": sustainability,
            "final": final_score,
        },
        "expectedRevenuePerAcrePkr": expected_revenue,
        "revenueConfidence": revenue_confidence,
        "riskFactors": risk_factors,
        "dataSourcesUsed": data_sources,
    }


def rank_candidates(crops: list[dict[str, Any]], ctx: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    scored = [score_crop(crop, ctx) for crop in crops]
    scored.sort(key=lambda item: item["scores"]["final"], reverse=True)
    return scored[:limit]


def pick_reason(scored: dict[str, Any], season_label: str, soil_label: str) -> dict[str, Any]:
    scores = scored["scores"]
    dimensions = [
        ("app.crops.reason.suitability", scores["suitability"]),
        ("app.crops.reason.profit", scores["profitability"]),
        ("app.crops.reason.weather_fit", scores["weatherFit"]),
        ("app.crops.reason.sustainability", scores["sustainability"]),
        ("app.crops.reason.low_risk", 1 - scores["risk"]),
    ]
    dimensions.sort(key=lambda item: item[1], reverse=True)
    key, value = dimensions[0]
    if value < 0.55:
        return {"key": "app.crops.reason.generic", "params": {"crop": scored["crop"].get("nameEn")}}
    return {
        "key": key,
        "params": {
            "crop": scored["crop"].get("nameEn"),
            "soil": soil_label,
            "season": season_label,
        },
    }
