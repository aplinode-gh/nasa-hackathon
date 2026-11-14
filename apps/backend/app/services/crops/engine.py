"""Crop recommendation engine orchestration."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.session import execute, get_pool, query, query_one
from app.services.crops.catalogue import get_compatibility_by_crop, get_crops_by_season_and_budget, resolve_soil_type
from app.services.crops.common import SEASON_LABELS, SOIL_LABELS
from app.services.crops.scoring import pick_reason, rank_candidates
from app.services.weather.service import get_forecast

PAKISTAN_BOUNDS = {"latMin": 23.5, "latMax": 37.0, "lngMin": 60.5, "lngMax": 77.0}
BRACKET_ORDER = ["low", "medium", "high", "very_high"]
BRACKET_CAPS = {"low": 25000, "medium": 60000, "high": 120000, "very_high": 10**12}


class CropEngineError(Exception):
    """Domain error carrying API status/code details."""

    def __init__(self, code: str, message: str, status: int, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}


def _within_pakistan(lat: Any, lng: Any) -> bool:
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except Exception:
        return False
    return (
        PAKISTAN_BOUNDS["latMin"] <= lat_f <= PAKISTAN_BOUNDS["latMax"]
        and PAKISTAN_BOUNDS["lngMin"] <= lng_f <= PAKISTAN_BOUNDS["lngMax"]
    )


def _lowest_viable_bracket(requested: str, crops: list[dict[str, Any]]) -> str:
    if not crops:
        return "very_high"
    req_cap = BRACKET_CAPS.get(requested, BRACKET_CAPS["very_high"])
    if any(float(c.get("capitalRequirementPerAcrePkr") or 0) <= req_cap for c in crops):
        return requested
    for bracket in BRACKET_ORDER:
        cap = BRACKET_CAPS[bracket]
        if any(float(c.get("capitalRequirementPerAcrePkr") or 0) <= cap for c in crops):
            return bracket
    return "very_high"


def _request_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "farmId": row.get("farm_id"),
        "targetSeason": row.get("target_season"),
        "targetYear": row.get("target_year"),
        "soilType": row.get("soil_type"),
        "soilIsRegionalDefault": bool(row.get("soil_is_regional_default")),
        "irrigationType": row.get("irrigation_type"),
        "budgetBracket": row.get("budget_bracket"),
        "confidence": {
            "weather": row.get("weather_confidence"),
            "market": row.get("market_confidence"),
            "soil": row.get("soil_confidence"),
        },
        "createdAt": row.get("created_at"),
    }


async def recommend_crops(input_data: dict[str, Any], account_id: str) -> dict[str, Any]:
    # Validate farm ownership and location context.
    farm = await query_one(
        "SELECT id, account_id, district, lat, lng FROM farms WHERE id = $1",
        input_data["farm_id"],
    )
    if not farm:
        raise CropEngineError("not_found", "Farm not found.", 404)
    if str(farm.get("account_id")) != str(account_id):
        raise CropEngineError("forbidden", "Farm does not belong to the account.", 403)
    if not _within_pakistan(farm.get("lat"), farm.get("lng")):
        raise CropEngineError("outside_pakistan", "Farm coordinates are outside Pakistan.", 422)

    existing = await query_one(
        """
        SELECT * FROM crop_recommendation_requests
        WHERE account_id = $1 AND farm_id = $2 AND target_season = $3 AND target_year = $4
        """,
        account_id,
        input_data["farm_id"],
        input_data["target_season"],
        input_data["target_year"],
    )
    if existing and not input_data.get("regenerate"):
        raise CropEngineError(
            "recommendation_exists",
            "You already have a recommendation for this farm, season, and year.",
            409,
            {"existing": _request_payload(existing)},
        )
    if existing and input_data.get("regenerate"):
        await execute("DELETE FROM crop_recommendation_requests WHERE id = $1", existing["id"])

    # Gather inputs and supporting data.
    resolved = await resolve_soil_type(input_data["soil_type"], farm.get("district") or "")
    forecast = await get_forecast(float(farm["lat"]), float(farm["lng"]))
    if not forecast:
        raise CropEngineError(
            "service_unavailable",
            "Weather forecast is unavailable and no cached advisory exists.",
            503,
        )

    price_rows = await query(
        """
        SELECT crop_id, price_per_maan_pkr, trend, volatility, observed_at
        FROM crop_price_trends
        ORDER BY crop_id, observed_at DESC
        """
    )
    latest_price_by_crop: dict[str, dict[str, Any]] = {}
    for row in price_rows or []:
        crop_id = str(row.get("crop_id"))
        if crop_id not in latest_price_by_crop:
            latest_price_by_crop[crop_id] = row
    market_available = len(latest_price_by_crop) > 0

    catalogue = await get_crops_by_season_and_budget(input_data["target_season"], input_data["budget_bracket"])
    if not catalogue:
        all_season = await get_crops_by_season_and_budget(input_data["target_season"], "very_high")
        raise CropEngineError(
            "no_candidates",
            "No crops found for this season and budget. Try adjusting your filters.",
            422,
            {"lowestViableBracket": _lowest_viable_bracket(input_data["budget_bracket"], all_season)},
        )

    compatibility = await get_compatibility_by_crop(resolved["soilType"])

    # Estimate freshness from latest market observations.
    data_freshness_seconds = 0
    if market_available:
        now_ts = datetime.now(timezone.utc).timestamp()
        for row in latest_price_by_crop.values():
            observed = row.get("observed_at")
            try:
                if isinstance(observed, datetime):
                    dt = observed if observed.tzinfo else observed.replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
                age = max(0, int(now_ts - dt.timestamp()))
                data_freshness_seconds = max(data_freshness_seconds, age)
            except Exception:
                pass

    past_crop = await query_one(
        """
        SELECT c.category
        FROM farms f
        JOIN crops c ON LOWER(c.name_en) = LOWER(f.primary_crop)
        WHERE f.id = $1
        LIMIT 1
        """,
        input_data["farm_id"],
    )

    ctx = {
        "soilType": resolved["soilType"],
        "season": input_data["target_season"],
        "budget": input_data["budget_bracket"],
        "irrigation": input_data["irrigation_type"],
        "weatherAvailable": True,
        "marketAvailable": market_available,
        "soilConfidence": "full" if resolved.get("note") == "exact" else "degraded",
        "compatibilityByCrop": compatibility,
        "priceByCrop": {
            crop_id: {
                "pricePerMaanPkr": float(row.get("price_per_maan_pkr") or 0),
                "trend": row.get("trend") or "stable",
                "volatility": float(row.get("volatility") or 0),
            }
            for crop_id, row in latest_price_by_crop.items()
        },
        "lastCropCategory": (past_crop or {}).get("category"),
    }

    ranked = rank_candidates(catalogue, ctx, 3)
    request_id = str(uuid.uuid4())

    # Persist request and ranked recommendations atomically.
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            req_row = await conn.fetchrow(
                """
                INSERT INTO crop_recommendation_requests
                  (id, account_id, farm_id, target_season, target_year, soil_type,
                   soil_is_regional_default, irrigation_type, budget_bracket,
                   weather_confidence, market_confidence, soil_confidence,
                   inputs_snapshot, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                RETURNING *
                """,
                request_id,
                account_id,
                input_data["farm_id"],
                input_data["target_season"],
                int(input_data["target_year"]),
                resolved["soilType"],
                bool(resolved["isRegionalDefault"]),
                input_data["irrigation_type"],
                input_data["budget_bracket"],
                "full",
                "full" if market_available else "missing",
                "full" if resolved.get("note") == "exact" else "degraded",
                json.dumps(input_data),
                datetime.now(timezone.utc),
            )

            recommendations: list[dict[str, Any]] = []
            for rank, item in enumerate(ranked, start=1):
                reason = pick_reason(
                    item,
                    SEASON_LABELS.get(input_data["target_season"], str(input_data["target_season"])),
                    SOIL_LABELS.get(resolved["soilType"], str(resolved["soilType"])),
                )
                rec_row = await conn.fetchrow(
                    """
                    INSERT INTO crop_recommendations
                      (id, request_id, rank, crop_id, expected_revenue_per_acre_pkr,
                       revenue_confidence, reason_key, risk_factors,
                       water_requirement_level, suitability_score, weather_fit_score,
                       profitability_score, risk_score, sustainability_score, final_score,
                       data_sources_used, data_fresheness_seconds, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
                    RETURNING *
                    """,
                    str(uuid.uuid4()),
                    request_id,
                    rank,
                    item["crop"]["id"],
                    float(item["expectedRevenuePerAcrePkr"]),
                    item["revenueConfidence"],
                    reason["key"],
                    item["riskFactors"],
                    item["crop"].get("waterRequirementLevel"),
                    float(item["scores"]["suitability"]),
                    float(item["scores"]["weatherFit"]),
                    float(item["scores"]["profitability"]),
                    float(item["scores"]["risk"]),
                    float(item["scores"]["sustainability"]),
                    float(item["scores"]["final"]),
                    item["dataSourcesUsed"],
                    int(data_freshness_seconds),
                    datetime.now(timezone.utc),
                )
                recommendations.append(
                    {
                        "id": rec_row["id"],
                        "rank": rec_row["rank"],
                        "crop": item["crop"],
                        "expectedRevenuePerAcrePkr": float(rec_row["expected_revenue_per_acre_pkr"]),
                        "revenueConfidence": rec_row["revenue_confidence"],
                        "reasonKey": rec_row["reason_key"],
                        "riskFactors": list(rec_row["risk_factors"] or []),
                        "waterRequirementLevel": rec_row["water_requirement_level"],
                        "scores": {
                            "suitability": float(rec_row["suitability_score"]),
                            "weatherFit": float(rec_row["weather_fit_score"]),
                            "profitability": float(rec_row["profitability_score"]),
                            "risk": float(rec_row["risk_score"]),
                            "sustainability": float(rec_row["sustainability_score"]),
                            "final": float(rec_row["final_score"]),
                        },
                        "dataSourcesUsed": list(rec_row["data_sources_used"] or []),
                        "dataFreshnessSeconds": int(rec_row["data_fresheness_seconds"] or 0),
                    }
                )

    return {
        "request": _request_payload(dict(req_row)),
        "recommendations": recommendations,
        "agentAnalysis": None,
    }
