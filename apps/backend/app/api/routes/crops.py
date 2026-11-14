"""Crop recommendation and planning API routes."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.core import rate_limit
from app.core.deps import require_session
from app.core.http import client_ip, error_response, read_json_body, success
from app.core.serialization import to_jsonable
from app.db.session import execute, get_pool, query, query_one
from app.models.crops import CropCatalogueQuery, CreateCropRecommendationRequest, SaveRecommendationRequest
from app.services.crops.catalogue import list_crops
from app.services.crops.common import map_crop_row
from app.services.crops.engine import CropEngineError, recommend_crops
from app.services.crops.rotation import build_rotation

router = APIRouter(prefix="/crops", tags=["crops"])


def _map_recommendation_row(row: dict[str, Any]) -> dict[str, Any]:
    crop = map_crop_row(
        {
            "id": row.get("crop_id"),
            "name_en": row.get("name_en"),
            "name_key": row.get("name_key"),
            "category": row.get("category"),
            "typical_yield_per_acre_kg": row.get("typical_yield_per_acre_kg"),
            "growing_duration_days": row.get("growing_duration_days"),
            "season_windows": row.get("season_windows"),
            "water_requirement_level": row.get("water_requirement_level"),
            "labour_cost_level": row.get("labour_cost_level"),
            "capital_requirement_per_acre_pkr": row.get("capital_requirement_per_acre_pkr"),
            "market_risk_baseline": row.get("market_risk_baseline"),
        }
    )
    return {
        "id": row.get("id"),
        "rank": row.get("rank"),
        "crop": crop,
        "expectedRevenuePerAcrePkr": float(row.get("expected_revenue_per_acre_pkr") or 0),
        "revenueConfidence": row.get("revenue_confidence"),
        "reasonKey": row.get("reason_key"),
        "riskFactors": row.get("risk_factors") or [],
        "waterRequirementLevel": row.get("water_requirement_level"),
        "scores": {
            "suitability": float(row.get("suitability_score") or 0),
            "weatherFit": float(row.get("weather_fit_score") or 0),
            "profitability": float(row.get("profitability_score") or 0),
            "risk": float(row.get("risk_score") or 0),
            "sustainability": float(row.get("sustainability_score") or 0),
            "final": float(row.get("final_score") or 0),
        },
        "dataSourcesUsed": row.get("data_sources_used") or [],
        "dataFreshnessSeconds": int(row.get("data_fresheness_seconds") or 0),
    }


@router.post("")
async def create_crop_recommendation(request: Request, session: dict = Depends(require_session)):
    try:
        ip = client_ip(request)
        now_ms = int(time.time() * 1000)
        if not rate_limit.hit("crops:ip", ip, 20, 3600000, now_ms=now_ms):
            return error_response("rate_limited", "Too many requests", 429)

        body = await read_json_body(request)
        parsed = CreateCropRecommendationRequest.model_validate(body or {})
        try:
            result = await recommend_crops(
                {
                    "farm_id": parsed.farm_id,
                    "target_season": parsed.target_season,
                    "target_year": parsed.target_year,
                    "soil_type": parsed.soil_type,
                    "irrigation_type": parsed.irrigation_type,
                    "budget_bracket": parsed.budget_bracket,
                    "regenerate": parsed.regenerate,
                },
                session["accountId"],
            )
            return success(to_jsonable(result), status_code=201)
        except CropEngineError as err:
            if err.code == "recommendation_exists":
                return success(
                    {
                        "error": {"code": err.code, "message": err.message},
                        "existing": err.extra.get("existing"),
                    },
                    status_code=err.status,
                )
            if err.code == "no_candidates":
                return success(
                    {
                        "error": {"code": err.code, "message": err.message},
                        "lowestViableBracket": err.extra.get("lowestViableBracket"),
                    },
                    status_code=err.status,
                )
            return error_response(err.code, err.message, err.status)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "target_year" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", "Something went wrong. Please try again.", 500)


@router.get("")
async def list_crop_recommendation_requests(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        farm_id = qp.get("farm_id")
        target_season = qp.get("target_season")
        target_year = qp.get("target_year")
        cursor = qp.get("cursor")
        try:
            limit = int(qp.get("limit", "20"))
        except Exception:
            return error_response("validation_error", "Invalid query", 422)
        if limit <= 0 or limit > 50:
            return error_response("validation_error", "Invalid query", 422)

        clauses = ["account_id = $1"]
        values: list[Any] = [session["accountId"]]
        idx = 2

        if farm_id:
            owner = await query_one("SELECT account_id FROM farms WHERE id = $1", farm_id)
            if not owner or str(owner.get("account_id")) != str(session["accountId"]):
                return error_response("forbidden", "Forbidden", 403)
            clauses.append(f"farm_id = ${idx}")
            values.append(farm_id)
            idx += 1
        if target_season:
            clauses.append(f"target_season = ${idx}")
            values.append(target_season)
            idx += 1
        if target_year:
            try:
                clauses.append(f"target_year = ${idx}")
                values.append(int(target_year))
                idx += 1
            except Exception:
                return error_response("validation_error", "Invalid query", 422)
        if cursor:
            clauses.append(f"created_at < (SELECT created_at FROM crop_recommendation_requests WHERE id = ${idx})")
            values.append(cursor)
            idx += 1

        rows = await query(
            f"""
            SELECT * FROM crop_recommendation_requests
            WHERE {" AND ".join(clauses)}
            ORDER BY created_at DESC
            LIMIT ${idx}
            """,
            *values,
            limit + 1,
        )
        rows = rows or []
        has_more = len(rows) > limit
        data = rows[:limit] if has_more else rows
        next_cursor = data[-1].get("id") if has_more and data else None

        requests_out = []
        for item in data:
            count_row = await query_one(
                "SELECT count(*)::text AS count FROM crop_recommendations WHERE request_id = $1",
                item.get("id"),
            )
            request_item = dict(item)
            request_item["recommendation_count"] = int((count_row or {}).get("count") or 0)
            requests_out.append(request_item)

        return success({"requests": to_jsonable(requests_out), "next_cursor": next_cursor})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/catalogue")
async def get_crop_catalogue(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        parsed = CropCatalogueQuery.model_validate(
            {"season": qp.get("season"), "category": qp.get("category"), "locale": qp.get("locale")}
        )
        crops = await list_crops(parsed.season, parsed.category)
        return success({"crops": to_jsonable(crops)})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", str(err), 500)


@router.get("/saved")
async def list_saved_plans(session: dict = Depends(require_session)):
    try:
        plans = await query(
            """
            SELECT fpe.id, fpe.farm_id, fpe.recommendation_id, fpe.target_season, fpe.target_year,
                   fpe.created_at, fpe.updated_at,
                   f.name AS farm_name, c.name_en AS crop_name
            FROM farm_plan_entries fpe
            JOIN farms f ON f.id = fpe.farm_id
            JOIN crop_recommendations cr ON cr.id = fpe.recommendation_id
            JOIN crops c ON c.id = cr.crop_id
            WHERE fpe.account_id = $1
            ORDER BY fpe.updated_at DESC
            """,
            session["accountId"],
        )
        return success({"plans": to_jsonable(plans or [])})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/save")
async def get_saved_plan(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        farm_id = qp.get("farm_id")
        season = qp.get("season")
        year = qp.get("year")
        if not farm_id or not season or not year:
            return error_response("validation_error", "farm_id, season and year are required", 422)
        try:
            year_int = int(year)
        except Exception:
            return error_response("validation_error", "Invalid year", 422)

        farm = await query_one("SELECT account_id FROM farms WHERE id = $1", farm_id)
        if not farm or str(farm.get("account_id")) != str(session["accountId"]):
            return error_response("forbidden", "Forbidden", 403)

        plan = await query_one(
            "SELECT * FROM farm_plan_entries WHERE farm_id = $1 AND target_season = $2 AND target_year = $3",
            farm_id,
            season,
            year_int,
        )
        if not plan:
            return error_response("not_found", "No saved plan", 404)

        rec = await query_one("SELECT * FROM crop_recommendations WHERE id = $1", plan.get("recommendation_id"))
        if not rec:
            return error_response("not_found", "Recommendation not found", 404)

        rotations = await query(
            """
            SELECT rs.*, c.id AS crop_id, c.name_en, c.name_key, c.category,
                   c.typical_yield_per_acre_kg, c.growing_duration_days, c.season_windows,
                   c.water_requirement_level, c.labour_cost_level,
                   c.capital_requirement_per_acre_pkr, c.market_risk_baseline
            FROM crop_rotation_suggestions rs
            JOIN crops c ON c.id = rs.crop_id
            WHERE rs.farm_plan_entry_id = $1
            ORDER BY rs.sequence_position ASC
            """,
            plan.get("id"),
        )
        rotation_suggestions = []
        for item in rotations or []:
            rotation_suggestions.append(
                {
                    "sequencePosition": item.get("sequence_position"),
                    "targetSeason": item.get("target_season"),
                    "targetYear": item.get("target_year"),
                    "crop": map_crop_row(item),
                    "reasonKey": item.get("reason_key"),
                    "isGeneric": item.get("is_generic"),
                }
            )
        return success(
            {
                "farm_plan_entry": to_jsonable(plan),
                "rotation_suggestions": to_jsonable(rotation_suggestions),
            }
        )
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/save")
async def save_recommendation(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = SaveRecommendationRequest.model_validate(body or {})

        rec = await query_one(
            """
            SELECT r.id, r.crop_id, req.farm_id, req.target_season, req.target_year
            FROM crop_recommendations r
            JOIN crop_recommendation_requests req ON req.id = r.request_id
            WHERE r.id = $1
            """,
            parsed.recommendation_id,
        )
        if not rec:
            return error_response("not_found", "Recommendation not found", 404)

        farm = await query_one("SELECT account_id FROM farms WHERE id = $1", rec.get("farm_id"))
        if not farm or str(farm.get("account_id")) != str(session["accountId"]):
            return error_response("forbidden", "Forbidden", 403)

        crop_row = await query_one("SELECT * FROM crops WHERE id = $1", rec.get("crop_id"))
        if not crop_row:
            return error_response("not_found", "Crop not found", 404)
        crop_summary = map_crop_row(crop_row)
        all_crops = [map_crop_row(row) for row in (await query("SELECT * FROM crops") or [])]

        past_crop = await query_one(
            """
            SELECT c.category
            FROM records r
            JOIN crops c ON c.name_en = r.crop
            WHERE r.farm_id = $1
            ORDER BY r.event_date DESC
            LIMIT 1
            """,
            rec.get("farm_id"),
        )
        has_history = bool((past_crop or {}).get("category"))
        rotations = await build_rotation(
            crop_summary,
            str(rec.get("target_season")),
            int(rec.get("target_year") or 0),
            has_history,
            all_crops,
        )

        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                plan_row = await conn.fetchrow(
                    """
                    INSERT INTO farm_plan_entries
                      (id, account_id, farm_id, recommendation_id, target_season, target_year, created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,now(),now())
                    ON CONFLICT (farm_id, target_season, target_year)
                    DO UPDATE SET recommendation_id = EXCLUDED.recommendation_id, updated_at = now()
                    RETURNING *
                    """,
                    str(uuid.uuid4()),
                    session["accountId"],
                    rec.get("farm_id"),
                    parsed.recommendation_id,
                    rec.get("target_season"),
                    rec.get("target_year"),
                )
                await conn.execute("DELETE FROM crop_rotation_suggestions WHERE farm_plan_entry_id = $1", plan_row["id"])

                saved_rotations = []
                for rot in rotations:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO crop_rotation_suggestions
                          (id, farm_plan_entry_id, sequence_position, target_season, target_year,
                           crop_id, reason_key, is_generic, created_at)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,now())
                        RETURNING *
                        """,
                        str(uuid.uuid4()),
                        plan_row["id"],
                        rot["sequencePosition"],
                        rot["targetSeason"],
                        rot["targetYear"],
                        rot["crop"]["id"],
                        rot["reasonKey"],
                        rot["isGeneric"],
                    )
                    saved_rotations.append(
                        {
                            "sequencePosition": row["sequence_position"],
                            "targetSeason": row["target_season"],
                            "targetYear": row["target_year"],
                            "crop": rot["crop"],
                            "reasonKey": row["reason_key"],
                            "isGeneric": row["is_generic"],
                        }
                    )

        plan = {
            "id": plan_row["id"],
            "farmId": plan_row["farm_id"],
            "recommendationId": plan_row["recommendation_id"],
            "targetSeason": plan_row["target_season"],
            "targetYear": plan_row["target_year"],
            "rotationSuggestions": saved_rotations,
        }
        return success({"farm_plan_entry": to_jsonable(plan), "rotation_suggestions": to_jsonable(saved_rotations)})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", str(err), 500)


@router.get("/{request_id}")
async def get_crop_recommendation(request_id: str, session: dict = Depends(require_session)):
    try:
        req = await query_one("SELECT * FROM crop_recommendation_requests WHERE id = $1", request_id)
        if not req:
            return error_response("not_found", "Not found", 404)

        farm = await query_one("SELECT account_id FROM farms WHERE id = $1", req.get("farm_id"))
        if not farm or str(farm.get("account_id")) != str(session["accountId"]):
            return error_response("forbidden", "Forbidden", 403)

        recs = await query(
            """
            SELECT r.*, c.id AS crop_id, c.name_en, c.name_key, c.category,
                   c.typical_yield_per_acre_kg, c.growing_duration_days, c.season_windows,
                   c.water_requirement_level, c.labour_cost_level,
                   c.capital_requirement_per_acre_pkr, c.market_risk_baseline
            FROM crop_recommendations r
            JOIN crops c ON c.id = r.crop_id
            WHERE r.request_id = $1
            ORDER BY r.rank ASC
            """,
            request_id,
        )
        recommendations = [_map_recommendation_row(row) for row in (recs or [])]
        return success({"request": to_jsonable(req), "recommendations": to_jsonable(recommendations)})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.delete("/{request_id}")
async def delete_crop_recommendation(request_id: str, session: dict = Depends(require_session)):
    try:
        existing = await query_one(
            """
            SELECT r.farm_id, f.account_id
            FROM crop_recommendation_requests r
            JOIN farms f ON f.id = r.farm_id
            WHERE r.id = $1
            """,
            request_id,
        )
        if not existing:
            return error_response("not_found", "Not found", 404)
        if str(existing.get("account_id")) != str(session["accountId"]):
            return error_response("forbidden", "Forbidden", 403)
        await execute("DELETE FROM crop_recommendation_requests WHERE id = $1", request_id)
        return Response(status_code=204)
    except Exception as err:
        return error_response("server_error", str(err), 500)
