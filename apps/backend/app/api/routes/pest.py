"""Pest risk forecast and alert routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.core.deps import require_session
from app.core.http import error_response, read_json_body, success
from app.core.serialization import parse_json_field, to_jsonable
from app.db.session import execute, query, query_one
from app.models.pest import GrowthStageRequest
from app.services.pest import alert_payload, build_forecast, stage_merge
from app.services.weather.service import get_forecast

router = APIRouter(prefix="/pest", tags=["pest"])


async def _owned_farm(farm_id: str, account_id: str):
    return await query_one(
        """
        SELECT id, name, district, lat, lng, crops, growth_stages, primary_crop
        FROM farms
        WHERE id = $1 AND account_id = $2 AND archived_at IS NULL
        """,
        farm_id,
        account_id,
    )


def _pick_crop(farm: dict[str, Any], requested: str | None) -> str:
    if requested:
        return requested
    if farm.get("primary_crop"):
        return str(farm["primary_crop"])
    crops = parse_json_field(farm.get("crops"), [])
    if isinstance(crops, list) and crops:
        return str(crops[0])
    return "wheat"


@router.get("/forecast")
async def pest_forecast(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        farm_id = qp.get("farm_id")
        if not farm_id:
            return error_response("validation_error", "farm_id is required", 422)

        farm = await _owned_farm(farm_id, session["accountId"])
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        crop = _pick_crop(farm, qp.get("crop"))
        lat = farm.get("lat")
        lng = farm.get("lng")
        weather = None
        if lat is not None and lng is not None:
            weather = await get_forecast(float(lat), float(lng))

        forecast = build_forecast(farm, crop, weather)

        for day in forecast["days"]:
            payload = alert_payload(farm, crop, day)
            if not payload:
                continue
            recent = await query_one(
                """
                SELECT id FROM pest_alerts
                WHERE farm_id = $1 AND pest_type = $2 AND created_at > now() - interval '24 hours'
                """,
                farm["id"],
                payload["pest_type"],
            )
            if recent:
                continue
            await execute(
                """
                INSERT INTO pest_alerts (
                  account_id, farm_id, crop, pest_type, risk_score, severity,
                  recommendation_text, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                session["accountId"],
                farm["id"],
                crop,
                payload["pest_type"],
                payload["risk_score"],
                payload["severity"],
                payload["recommendation_text"],
                payload["status"],
            )

        return success(to_jsonable(forecast))
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/alerts")
async def list_alerts(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        try:
            limit = int(qp.get("limit", "20"))
        except Exception:
            return error_response("validation_error", "Invalid query", 422)
        if limit <= 0 or limit > 100:
            return error_response("validation_error", "Invalid query", 422)

        values: list[Any] = [session["accountId"]]
        where = ["account_id = $1"]
        idx = 2
        farm_id = qp.get("farm_id")
        if farm_id:
            where.append(f"farm_id = ${idx}")
            values.append(farm_id)
            idx += 1

        rows = await query(
            f"""
            SELECT id, farm_id, crop, pest_type, risk_score, severity,
                   recommendation_text, status, created_at, read_at
            FROM pest_alerts
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT ${idx}
            """,
            *values,
            limit,
        )
        return success(to_jsonable(rows or []))
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, session: dict = Depends(require_session)):
    try:
        row = await query_one(
            """
            UPDATE pest_alerts
            SET read_at = now()
            WHERE id = $1 AND account_id = $2 AND read_at IS NULL
            RETURNING id
            """,
            alert_id,
            session["accountId"],
        )
        if not row:
            existing = await query_one(
                "SELECT id FROM pest_alerts WHERE id = $1 AND account_id = $2",
                alert_id,
                session["accountId"],
            )
            if not existing:
                return error_response("not_found", "Alert not found", 404)
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/growth-stage")
async def update_growth_stage(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = GrowthStageRequest.model_validate(body or {})
        farm = await _owned_farm(parsed.farm_id, session["accountId"])
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        merged = stage_merge(farm.get("growth_stages"), parsed.crop, parsed.stage)
        await execute(
            "UPDATE farms SET growth_stages = $1, updated_at = now() WHERE id = $2 AND account_id = $3",
            json.dumps(merged),
            parsed.farm_id,
            session["accountId"],
        )
        return success({"ok": True})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)
