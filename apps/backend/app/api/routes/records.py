"""Farm activity record API routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.core.deps import require_session
from app.core.http import error_response, read_json_body, success
from app.core.serialization import parse_json_field, to_jsonable
from app.db.session import execute, query, query_one
from app.models.farms import CreateRecordRequest, UpdateRecordRequest
from app.services.farms.growth_stages import auto_advance_stage
from app.services.farms.weather import fetch_current_weather

router = APIRouter(prefix="/records", tags=["records"])


def _as_crops(value: Any) -> list[str]:
    parsed = parse_json_field(value, [])
    return [str(x) for x in parsed] if isinstance(parsed, list) else []


def _as_stage_map(value: Any) -> dict[str, str]:
    parsed = parse_json_field(value, {})
    if isinstance(parsed, dict):
        return {str(k): str(v) for k, v in parsed.items()}
    return {}


async def _get_owned_record(record_id: str, account_id: str):
    return await query_one(
        """
        SELECT r.* FROM records r
        JOIN farms f ON f.id = r.farm_id
        WHERE r.id = $1 AND f.account_id = $2 AND f.archived_at IS NULL
        """,
        record_id,
        account_id,
    )


@router.post("")
async def create_record(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = CreateRecordRequest.model_validate(body or {})

        farm = await query_one(
            """
            SELECT lat, lng, crops, growth_stages, name FROM farms
            WHERE id = $1 AND account_id = $2 AND archived_at IS NULL
            """,
            parsed.farm_id,
            session["accountId"],
        )
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        weather_condition = parsed.weather_condition
        if not weather_condition and farm.get("lat") is not None and farm.get("lng") is not None:
            fetched = await fetch_current_weather(float(farm["lat"]), float(farm["lng"]), parsed.event_date)
            weather_snapshot = {**fetched, "condition": fetched.get("condition") or weather_condition}
        elif weather_condition:
            weather_snapshot = {
                "condition": weather_condition,
                "temp_c": None,
                "humidity": None,
                "wind_kph": None,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            weather_snapshot = {
                "condition": None,
                "temp_c": None,
                "humidity": None,
                "wind_kph": None,
                "fetched_at": None,
            }

        crops = _as_crops(farm.get("crops"))
        growth_stages = _as_stage_map(farm.get("growth_stages"))
        for crop in crops:
            growth_stages = auto_advance_stage(growth_stages, parsed.type, crop)

        # Insert record and update farm stages in sequence.
        record = await query_one(
            """
            INSERT INTO records (
                account_id, farm_id, type, season, year, event_date,
                title, note, weather, yield_qty, labor_cost, transport_cost
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            session["accountId"],
            parsed.farm_id,
            parsed.type,
            parsed.season,
            parsed.year,
            parsed.event_date,
            parsed.title,
            parsed.note,
            json.dumps(weather_snapshot),
            parsed.yield_qty,
            parsed.labor_cost,
            parsed.transport_cost,
        )
        await execute(
            "UPDATE farms SET growth_stages = $1, updated_at = now() WHERE id = $2",
            json.dumps(growth_stages),
            parsed.farm_id,
        )

        return success(to_jsonable(record), status_code=201)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.patch("/{record_id}")
async def update_record(record_id: str, request: Request, session: dict = Depends(require_session)):
    try:
        record = await _get_owned_record(record_id, session["accountId"])
        if not record:
            return error_response("not_found", "Record not found", 404)

        body = await read_json_body(request)
        parsed = UpdateRecordRequest.model_validate(body or {})
        payload = parsed.model_dump(exclude_unset=True)

        if "weather_condition" in payload:
            existing_weather = parse_json_field(record.get("weather"), {})
            if not isinstance(existing_weather, dict):
                existing_weather = {}
            payload["weather"] = json.dumps(
                {
                    **existing_weather,
                    "condition": payload.get("weather_condition"),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            payload.pop("weather_condition", None)

        if not payload:
            return success(to_jsonable(record))

        set_clauses = []
        values: list[Any] = []
        idx = 1
        for key, value in payload.items():
            set_clauses.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
        values.append(record_id)

        data = await query_one(
            f"UPDATE records SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *",
            *values,
        )
        if not data:
            return error_response("server_error", "Failed to update record", 500)
        return success(to_jsonable(data))
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.delete("/{record_id}")
async def delete_record(record_id: str, session: dict = Depends(require_session)):
    try:
        record = await _get_owned_record(record_id, session["accountId"])
        if not record:
            return error_response("not_found", "Record not found", 404)
        await execute("DELETE FROM records WHERE id = $1", record_id)
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)
