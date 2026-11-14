"""Weather and advisory API routes."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.core.deps import require_session
from app.core.http import error_response, read_json_body, success
from app.core.serialization import parse_json_field, to_jsonable
from app.db.session import query, query_one
from app.models.weather import AcknowledgeRequest, HistoryQuery, RegisterWeatherRequest
from app.services.farms.weather import fetch_current_weather
from app.services.weather.service import (
    advice_text_for_key,
    build_advisory_days,
    decode_cursor,
    encode_cursor,
    get_forecast,
    run_alert_scan,
)

router = APIRouter(prefix="/weather", tags=["weather"])


def _effective_crop_info(farm: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, str] | None:
    sowing_records = [r for r in records if r.get("type") in ("sowing", "planting")]
    latest_sowing = sowing_records[0] if sowing_records else None
    if latest_sowing and farm.get("primary_crop"):
        event_date = latest_sowing.get("event_date")
        return {"crop": str(farm["primary_crop"]), "sowingDate": str(event_date)}
    if farm.get("primary_crop") and farm.get("sowing_date"):
        return {"crop": str(farm["primary_crop"]), "sowingDate": str(farm["sowing_date"])}
    return None


@router.post("/register")
async def register_weather(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = RegisterWeatherRequest.model_validate(body or {})

        try:
            sowing_dt = datetime.fromisoformat(parsed.sowing_date.replace("Z", "+00:00"))
        except Exception:
            return error_response("validation_error", "Invalid sowing date", 422)
        today = datetime.now(timezone.utc).date()
        sowing_date_only = sowing_dt.date()
        if sowing_date_only >= today:
            return error_response("validation_error", "Sowing date must be in the past", 422)

        farm = await query_one(
            "SELECT id FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL",
            parsed.farm_id,
            session["accountId"],
        )
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        updated = await query_one(
            """
            UPDATE farms
            SET primary_crop = $1, sowing_date = $2, soil_type = $3, irrigation_method = $4, updated_at = now()
            WHERE id = $5 AND account_id = $6
            RETURNING id, primary_crop, sowing_date, soil_type, irrigation_method
            """,
            parsed.primary_crop,
            sowing_date_only.isoformat(),
            parsed.soil_type,
            parsed.irrigation_method,
            parsed.farm_id,
            session["accountId"],
        )
        if not updated:
            return error_response("server_error", "Failed to update farm", 500)
        return success(to_jsonable(updated), status_code=200)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.get("/current")
async def get_current_weather(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        try:
            lat = float(qp.get("lat")) if qp.get("lat") is not None else None
            lng = float(qp.get("lng")) if qp.get("lng") is not None else None
        except Exception:
            lat = lng = None
        if lat is None or lng is None:
            return error_response("validation_error", "lat and lng are required", 422)
        snapshot = await fetch_current_weather(lat, lng)
        return success(to_jsonable(snapshot))
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/forecast")
async def get_weather_forecast(request: Request, session: dict = Depends(require_session)):
    try:
        farm_id = request.query_params.get("farm_id")
        if not farm_id:
            return error_response("validation_error", "farm_id is required", 422)

        farm = await query_one(
            """
            SELECT id, name, primary_crop, sowing_date, lat, lng, growth_stages
            FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL
            """,
            farm_id,
            session["accountId"],
        )
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        records = await query(
            "SELECT type, event_date FROM records WHERE farm_id = $1 AND account_id = $2 ORDER BY event_date DESC",
            farm["id"],
            session["accountId"],
        )
        effective_crop = _effective_crop_info(farm, records or [])
        today = datetime.now(timezone.utc).date().isoformat()
        forecast = await get_forecast(float(farm["lat"]), float(farm["lng"]))

        if not forecast:
            cached = await query_one(
                """
                SELECT advisory_date, growth_stage, advice_text, severity
                FROM weather_advisories WHERE farm_id = $1 AND advisory_date <= $2
                ORDER BY advisory_date DESC LIMIT 1
                """,
                farm["id"],
                today,
            )
            return success(
                {
                    "farm_id": str(farm["id"]),
                    "farm_name": farm.get("name"),
                    "weather_data_unavailable": True,
                    "today": to_jsonable(cached) if cached else None,
                    "days": [],
                }
            )

        if not effective_crop:
            return success(
                {
                    "farm_id": str(farm["id"]),
                    "farm_name": farm.get("name"),
                    "weather_data_unavailable": False,
                    "days": [],
                    "today": None,
                }
            )

        advisory_days = build_advisory_days(effective_crop["crop"], effective_crop["sowingDate"], forecast)
        today_advice = next((d for d in advisory_days if d["date"] == today), advisory_days[0] if advisory_days else None)
        if today_advice:
            snapshot = json.dumps(
                {
                    "source": forecast.get("source"),
                    "days": len(advisory_days),
                    "crop": effective_crop["crop"],
                    "sowingDate": effective_crop["sowingDate"],
                }
            )
            await query_one(
                """
                INSERT INTO weather_advisories (
                  farm_id, account_id, advisory_date, forecast_snapshot, growth_stage,
                  advice_key, advice_text, severity
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                ON CONFLICT (farm_id, advisory_date) DO UPDATE SET
                  forecast_snapshot = EXCLUDED.forecast_snapshot,
                  growth_stage = EXCLUDED.growth_stage,
                  advice_key = EXCLUDED.advice_key,
                  advice_text = EXCLUDED.advice_text,
                  severity = EXCLUDED.severity
                """,
                farm["id"],
                session["accountId"],
                today,
                snapshot,
                today_advice.get("growth_stage"),
                today_advice.get("advice_key"),
                today_advice.get("advice_text") or advice_text_for_key(str(today_advice.get("advice_key"))),
                today_advice.get("severity"),
            )

        return success(
            {
                "farm_id": str(farm["id"]),
                "farm_name": farm.get("name"),
                "weather_data_unavailable": False,
                "days": to_jsonable(advisory_days),
            }
        )
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/history")
async def get_weather_history(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        parsed = HistoryQuery.model_validate(
            {"farm_id": qp.get("farm_id"), "limit": qp.get("limit", 20), "cursor": qp.get("cursor")}
        )
        cursor_date, cursor_id = decode_cursor(parsed.cursor)
        rows = await query(
            """
            SELECT id, farm_id, advisory_date, growth_stage, advice_key, advice_text,
                   severity, acknowledged, acted_upon, created_at
            FROM weather_advisories
            WHERE farm_id = $1 AND account_id = $2
              AND ($3::text IS NULL OR advisory_date < $3
                   OR (advisory_date = $3 AND id < $4::uuid))
            ORDER BY advisory_date DESC, id DESC
            LIMIT $5
            """,
            parsed.farm_id,
            session["accountId"],
            cursor_date,
            cursor_id,
            parsed.limit + 1,
        )
        items = rows or []
        has_more = len(items) > parsed.limit
        page_items = items[: parsed.limit]
        next_cursor = None
        if has_more and page_items:
            last = page_items[-1]
            next_cursor = encode_cursor(str(last.get("advisory_date")), str(last.get("id")))
        mapped = []
        for r in page_items:
            mapped.append(
                {
                    "id": r.get("id"),
                    "farm_id": r.get("farm_id"),
                    "advisory_date": r.get("advisory_date"),
                    "growth_stage": r.get("growth_stage"),
                    "advice_key": r.get("advice_key"),
                    "advice_text": r.get("advice_text"),
                    "severity": r.get("severity"),
                    "acknowledged": r.get("acknowledged"),
                    "acted_upon": r.get("acted_upon"),
                }
            )
        return success({"items": to_jsonable(mapped), "next_cursor": next_cursor})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.post("/history/{advisory_id}/acknowledge")
async def acknowledge_weather(advisory_id: str, request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = AcknowledgeRequest.model_validate(body or {})
        acted = parsed.action == "acted_upon"
        row = await query_one(
            """
            UPDATE weather_advisories
            SET acknowledged = true, acted_upon = $3
            WHERE id = $1 AND account_id = $2
            RETURNING id
            """,
            advisory_id,
            session["accountId"],
            acted,
        )
        if not row:
            return error_response("not_found", "Advisory not found", 404)
        from fastapi.responses import Response

        return Response(status_code=204)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.get("/alerts")
async def list_weather_alerts(session: dict = Depends(require_session)):
    try:
        alerts = await query(
            """
            SELECT wa.id, wa.farm_id, f.name AS farm_name, wa.alert_type,
                   wa.recommendation_key, wa.recommendation, wa.severity,
                   wa.created_at, wa.read_at
            FROM weather_alerts wa
            JOIN farms f ON f.id = wa.farm_id
            WHERE wa.account_id = $1 AND wa.read_at IS NULL AND wa.dismissed_at IS NULL
            ORDER BY wa.created_at DESC
            """,
            session["accountId"],
        )
        mapped = []
        for a in alerts or []:
            mapped.append(
                {
                    "id": a.get("id"),
                    "farm_id": a.get("farm_id"),
                    "farm_name": a.get("farm_name"),
                    "alert_type": a.get("alert_type"),
                    "recommendation_key": a.get("recommendation_key"),
                    "recommendation": a.get("recommendation"),
                    "severity": a.get("severity"),
                    "created_at": a.get("created_at"),
                    "read": a.get("read_at") is not None,
                }
            )
        return success({"alerts": to_jsonable(mapped)})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/alerts/{alert_id}/read")
async def mark_weather_alert_read(alert_id: str, session: dict = Depends(require_session)):
    try:
        row = await query_one(
            """
            UPDATE weather_alerts SET read_at = now()
            WHERE id = $1 AND account_id = $2 AND read_at IS NULL
            RETURNING id
            """,
            alert_id,
            session["accountId"],
        )
        if not row:
            return error_response("not_found", "Alert not found", 404)
        from fastapi.responses import Response

        return Response(status_code=204)
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/alerts/trigger")
async def trigger_weather_alerts(request: Request):
    try:
        secret = os.getenv("ADVISOR_CRON_SECRET")
        auth = request.headers.get("authorization")
        if not secret or auth != f"Bearer {secret}":
            return error_response("unauthorized", "Unauthorized", 401)

        farms = await query(
            """
            SELECT f.id, f.account_id, f.name, f.lat, f.lng, u.email
            FROM farms f JOIN users u ON u.id = f.account_id
            WHERE f.archived_at IS NULL AND f.primary_crop IS NOT NULL
            """
        )
        scanned = 0
        alerts_created = 0
        for farm in farms or []:
            forecast = await get_forecast(float(farm["lat"]), float(farm["lng"]))
            if not forecast:
                continue
            scanned += 1
            created = await run_alert_scan(
                {
                    "farm_id": str(farm["id"]),
                    "account_id": str(farm["account_id"]),
                    "farm_name": farm.get("name"),
                },
                forecast,
                farm.get("email"),
            )
            alerts_created += len(created or [])
        return success({"scanned": scanned, "alerts_created": alerts_created})
    except Exception as err:
        return error_response("server_error", str(err), 500)
