"""Farm management API routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.core.deps import require_session
from app.core.http import error_response, read_json_body, success
from app.core.serialization import parse_json_field, to_jsonable
from app.db.session import execute, get_pool, query, query_one
from app.models.farms import CreateFarmRequest, UpdateFarmRequest
from app.services.farms.growth_stages import default_stages_for_crops
from app.services.farms.health import compute_farm_health

router = APIRouter(prefix="/farms", tags=["farms"])


def _as_crops(value: Any) -> list[str]:
    parsed = parse_json_field(value, [])
    if isinstance(parsed, list):
        return [str(x) for x in parsed]
    return []


def _as_stage_map(value: Any) -> dict[str, str]:
    parsed = parse_json_field(value, {})
    if isinstance(parsed, dict):
        return {str(k): str(v) for k, v in parsed.items()}
    return {}


@router.get("")
async def list_farms(session: dict = Depends(require_session)):
    try:
        farms = await query(
            """
            SELECT * FROM farms
            WHERE account_id = $1 AND archived_at IS NULL
            ORDER BY created_at DESC
            """,
            session["accountId"],
        )

        enriched = []
        for farm in farms or []:
            recent = await query(
                """
                SELECT type, event_date FROM records
                WHERE farm_id = $1
                ORDER BY event_date DESC
                LIMIT 5
                """,
                farm["id"],
            )
            seasons_rows = await query(
                "SELECT season, year FROM records WHERE farm_id = $1",
                farm["id"],
            )
            seasons_set = {f"{r.get('season')} {r.get('year')}" for r in (seasons_rows or []) if r.get("season") and r.get("year")}
            farm_out = dict(farm)
            farm_out["health"] = compute_farm_health(_as_stage_map(farm.get("growth_stages")), recent or [])
            farm_out["seasons"] = sorted(seasons_set)
            enriched.append(to_jsonable(farm_out))

        return success(enriched)
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("")
async def create_farm(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = CreateFarmRequest.model_validate(body or {})
        growth_stages = default_stages_for_crops(parsed.crops)
        primary_crop = parsed.primary_crop or parsed.crops[0]

        data = await query_one(
            """
            INSERT INTO farms (
                account_id, name, location, district, lat, lng, crops, acres, growth_stages,
                primary_crop, sowing_date, soil_type, irrigation_method
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
            """,
            session["accountId"],
            parsed.name,
            parsed.location,
            parsed.district,
            json.dumps(parsed.crops),
            parsed.acres,
            parsed.lat,
            parsed.lng,
            json.dumps(growth_stages),
            primary_crop,
            parsed.sowing_date,
            parsed.soil_type,
            parsed.irrigation_method,
        )
        if not data:
            return error_response("server_error", "Failed to create farm", 500)
        return success(to_jsonable(data), status_code=201)
    except Exception as err:
        # Pydantic validation errors and other issues -> 422/500 best effort
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg or "required" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


async def _get_owned_farm(farm_id: str, account_id: str):
    try:
        farm = await query_one(
            """
            SELECT * FROM farms
            WHERE id = $1 AND account_id = $2 AND archived_at IS NULL
            """,
            farm_id,
            account_id,
        )
        return farm, None
    except Exception as err:
        return None, err


@router.get("/{farm_id}")
async def get_farm(farm_id: str, session: dict = Depends(require_session)):
    try:
        farm, err = await _get_owned_farm(farm_id, session["accountId"])
        if err:
            return error_response("server_error", str(err), 500)
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        recent_records = await query(
            """
            SELECT * FROM records
            WHERE farm_id = $1
            ORDER BY event_date DESC, created_at DESC
            LIMIT 5
            """,
            farm_id,
        )
        out = dict(farm)
        out["recent_records"] = recent_records or []
        return success(to_jsonable(out))
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.patch("/{farm_id}")
async def update_farm(farm_id: str, request: Request, session: dict = Depends(require_session)):
    try:
        farm, err = await _get_owned_farm(farm_id, session["accountId"])
        if err:
            return error_response("server_error", str(err), 500)
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        body = await read_json_body(request)
        parsed = UpdateFarmRequest.model_validate(body or {})
        payload = parsed.model_dump(exclude_unset=True)
        payload.pop("client_uuid", None)

        if "growth_stages" in payload and payload["growth_stages"] is not None:
            merged = {**_as_stage_map(farm.get("growth_stages")), **(payload.get("growth_stages") or {})}
            payload["growth_stages"] = json.dumps(merged)
        elif "growth_stages" in payload:
            payload.pop("growth_stages", None)

        if "crops" in payload and payload["crops"] is not None:
            payload["crops"] = json.dumps(payload["crops"])

        if not payload:
            return success(to_jsonable(farm))

        set_clauses = []
        values: list[Any] = []
        idx = 1
        for key, value in payload.items():
            set_clauses.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
        set_clauses.append("updated_at = now()")
        values.extend([farm_id, session["accountId"]])

        data = await query_one(
            f"""
            UPDATE farms SET {", ".join(set_clauses)}
            WHERE id = ${idx} AND account_id = ${idx + 1}
            RETURNING *
            """,
            *values,
        )
        if not data:
            return error_response("server_error", "Failed to update farm", 500)
        return success(to_jsonable(data))
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.delete("/{farm_id}")
async def delete_farm(farm_id: str, session: dict = Depends(require_session)):
    try:
        farm, err = await _get_owned_farm(farm_id, session["accountId"])
        if err:
            return error_response("server_error", str(err), 500)
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        count_row = await query_one("SELECT count(*)::text as count FROM records WHERE farm_id = $1", farm_id)
        if int((count_row or {}).get("count") or 0) > 0:
            return error_response("conflict", "Delete all records first.", 409)

        await execute("DELETE FROM farms WHERE id = $1", farm_id)
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/{farm_id}/records")
async def list_farm_records(
    farm_id: str,
    request: Request,
    session: dict = Depends(require_session),
):
    try:
        farm = await query_one(
            "SELECT id FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL",
            farm_id,
            session["accountId"],
        )
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        params = request.query_params
        limit_raw = params.get("limit")
        try:
            limit = int(limit_raw) if limit_raw is not None else 20
        except Exception:
            return error_response("validation_error", "Invalid query params", 422)
        if limit <= 0 or limit > 100:
            return error_response("validation_error", "Invalid query params", 422)

        season = params.get("season")
        year = params.get("year")
        cursor = params.get("cursor")

        conditions = ["farm_id = $1"]
        values: list[Any] = [farm_id]
        idx = 2
        if season:
            conditions.append(f"season = ${idx}")
            values.append(season)
            idx += 1
        if year:
            conditions.append(f"year = ${idx}")
            values.append(year)
            idx += 1
        if cursor:
            parts = cursor.split("|", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                conditions.append(f"(event_date < ${idx} OR (event_date = ${idx} AND id < ${idx + 1}))")
                values.extend([parts[0], parts[1]])
                idx += 2

        rows = await query(
            f"""
            SELECT * FROM records
            WHERE {" AND ".join(conditions)}
            ORDER BY event_date DESC, created_at DESC
            LIMIT ${idx}
            """,
            *values,
            limit,
        )
        return success(to_jsonable(rows or []))
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/{farm_id}/archive")
async def archive_farm(farm_id: str, session: dict = Depends(require_session)):
    try:
        data = await query_one(
            """
            UPDATE farms
            SET archived_at = $1, updated_at = now()
            WHERE id = $2 AND account_id = $3 AND archived_at IS NULL
            RETURNING *
            """,
            datetime.now(timezone.utc),
            farm_id,
            session["accountId"],
        )
        if not data:
            return error_response("not_found", "Farm not found", 404)
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/{farm_id}/restore")
async def restore_farm(farm_id: str, session: dict = Depends(require_session)):
    try:
        data = await query_one(
            """
            UPDATE farms
            SET archived_at = NULL, updated_at = now()
            WHERE id = $1 AND account_id = $2 AND archived_at IS NOT NULL
            RETURNING *
            """,
            farm_id,
            session["accountId"],
        )
        if not data:
            return error_response("not_found", "Farm not found", 404)
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)
