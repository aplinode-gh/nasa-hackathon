"""Market price API routes."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from app.core import rate_limit
from app.core.deps import require_session
from app.core.http import client_ip, error_response, read_json_body, success
from app.core.serialization import to_jsonable
from app.db.session import execute, get_pool, query, query_one
from app.models.prices import (
    AlertCreateRequest,
    AlertUpdateRequest,
    CreatePriceRequest,
    GetPricesQuery,
    HistoryQuery,
    PredictionQuery,
)
from app.services.prices.forecast import can_forecast, forecast_prices
from app.services.prices.proximity import haversine_km, resolve_district_context
from app.services.prices.transport import estimate_transport_cost

router = APIRouter(prefix="/prices", tags=["prices"])

RANGE_DAYS = {"1M": 30, "3M": 90, "6M": 180, "12M": 365}


def _crop_name_column(request: Request) -> str:
    locale = request.cookies.get("locale") or (request.headers.get("accept-language") or "en")[:2]
    loc = (locale or "en").strip().lower()
    if not loc.isalpha() or len(loc) not in (2, 3):
        loc = "en"
    return f"name_{loc}"


def _dedupe_latest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = f"{row.get('mandi_id')}:{row.get('crop_id')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _enrich_prices(rows: list[dict[str, Any]], farm_lat: Any, farm_lng: Any) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        prev = float(row["prev_modal"]) if row.get("prev_modal") is not None else None
        current = float(row.get("modal_price") or 0)
        change_pkr = round((current - prev) * 100) / 100 if prev is not None else 0.0
        change_pct = round((change_pkr / prev) * 1000) / 10 if prev not in (None, 0) else 0.0

        distance_km = None
        if (
            farm_lat is not None
            and farm_lng is not None
            and row.get("latitude") is not None
            and row.get("longitude") is not None
        ):
            try:
                distance_km = haversine_km(
                    float(farm_lat), float(farm_lng), float(row["latitude"]), float(row["longitude"])
                )
            except Exception:
                distance_km = None

        enriched.append(
            {
                **row,
                "distance_km": distance_km,
                "change_pct": change_pct,
                "change_pkr": change_pkr,
                "is_best_price": False,
                "transport_cost_pkr": estimate_transport_cost(distance_km),
            }
        )
    return enriched


@router.get("")
async def get_prices(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        parsed = GetPricesQuery.model_validate(
            {
                "crop_id": qp.get("crop_id"),
                "district": qp.get("district"),
                "farm_id": qp.get("farm_id"),
                "query": qp.get("query"),
                "include_bordering": qp.get("include_bordering", "true"),
            }
        )
        name_column = _crop_name_column(request)

        if parsed.query:
            like = f"%{parsed.query.lower()}%"
            rows = await query(
                f"""
                SELECT
                  m.id as mandi_id, m.name_en as mandi_name, m.district,
                  m.latitude, m.longitude,
                  c.id as crop_id, c.{name_column} as crop_name,
                  p.date, p.modal_price, p.min_price, p.max_price, p.unit, p.is_holiday, p.source_code,
                  current_date - p.date as updated_days_ago,
                  lag(p.modal_price) over (partition by p.mandi_id, p.crop_id order by p.date) as prev_modal
                FROM mandi_prices p
                JOIN mandis m ON m.id = p.mandi_id
                JOIN crops c ON c.id = p.crop_id
                WHERE (
                  lower(m.name_en) LIKE $1
                  OR lower(m.district) LIKE $1
                  OR lower(c.name_en) LIKE $1
                  OR lower(c.{name_column}) LIKE $1
                )
                ORDER BY p.date DESC, p.modal_price DESC
                LIMIT 50
                """,
                like,
            )
            return success(
                {
                    "district": None,
                    "is_fallback_hub": False,
                    "prices": to_jsonable(_enrich_prices(rows or [], None, None)),
                }
            )

        district = parsed.district
        farm_lat = None
        farm_lng = None

        if parsed.farm_id and not district:
            farm = await query_one(
                "SELECT district, lat, lng FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL",
                parsed.farm_id,
                session["accountId"],
            )
            if farm:
                district = farm.get("district") or district
                farm_lat = farm.get("lat")
                farm_lng = farm.get("lng")

        if not district:
            farm = await query_one(
                "SELECT district FROM farms WHERE account_id = $1 AND archived_at IS NULL ORDER BY created_at DESC LIMIT 1",
                session["accountId"],
            )
            district = (farm or {}).get("district")

        context = await resolve_district_context(district)
        districts = context["searchDistricts"] if parsed.include_bordering else [context["district"]]
        params: list[Any] = [districts]
        crop_filter = ""
        if parsed.crop_id:
            crop_filter = "AND c.id = $2"
            params.append(parsed.crop_id)

        rows = await query(
            f"""
            SELECT
              m.id as mandi_id, m.name_en as mandi_name, m.district,
              m.latitude, m.longitude,
              c.id as crop_id, c.{name_column} as crop_name,
              p.date, p.modal_price, p.min_price, p.max_price, p.unit, p.is_holiday, p.source_code,
              current_date - p.date as updated_days_ago,
              lag(p.modal_price) over (partition by p.mandi_id, p.crop_id order by p.date) as prev_modal
            FROM mandi_prices p
            JOIN mandis m ON m.id = p.mandi_id
            JOIN crops c ON c.id = p.crop_id
            WHERE m.district = ANY($1)
              {crop_filter}
            ORDER BY p.date DESC, p.modal_price DESC
            """,
            *params,
        )

        unique = _dedupe_latest(rows or [])
        eff_lat = farm_lat if farm_lat is not None else context.get("farmLat")
        eff_lng = farm_lng if farm_lng is not None else context.get("farmLng")
        enriched = _enrich_prices(unique, eff_lat, eff_lng)
        if enriched:
            best_modal = max(float(p.get("modal_price") or 0) for p in enriched)
            for p in enriched:
                p["is_best_price"] = float(p.get("modal_price") or 0) == best_modal

        return success(
            {
                "district": context.get("district"),
                "is_fallback_hub": bool(context.get("isFallbackHub", False)),
                "prices": to_jsonable(enriched),
            }
        )
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("")
async def create_price(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = CreatePriceRequest.model_validate(body or {})
        if parsed.min_price > parsed.modal_price or parsed.max_price < parsed.modal_price:
            return error_response("validation_error", "modal_price must be between min_price and max_price", 422)

        crop = await query_one("SELECT id FROM crops WHERE id = $1", parsed.crop_id)
        if not crop:
            return error_response("not_found", "Crop not found", 404)
        mandi = await query_one("SELECT id FROM mandis WHERE id = $1", parsed.mandi_id)
        if not mandi:
            return error_response("not_found", "Mandi not found", 404)

        await execute(
            """
            INSERT INTO mandi_prices (mandi_id, crop_id, date, modal_price, min_price, max_price, unit, is_holiday, source)
            VALUES ($1, $2, $3, $4, $5, $6, 'Maund', $7, 'manual')
            ON CONFLICT (mandi_id, crop_id, date)
            DO UPDATE SET modal_price = EXCLUDED.modal_price,
                          min_price = EXCLUDED.min_price,
                          max_price = EXCLUDED.max_price,
                          is_holiday = EXCLUDED.is_holiday,
                          source = 'manual'
            """,
            parsed.mandi_id,
            parsed.crop_id,
            parsed.date,
            parsed.modal_price,
            parsed.min_price,
            parsed.max_price,
            parsed.is_holiday,
        )
        return success({"success": True})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "modal_price" in msg or "date" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.get("/history")
async def get_price_history(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        parsed = HistoryQuery.model_validate(
            {"crop_id": qp.get("crop_id"), "mandi_id": qp.get("mandi_id"), "range": qp.get("range", "3M")}
        )
        days = RANGE_DAYS[parsed.range]
        rows = await query(
            """
            SELECT date, modal_price, min_price, max_price
            FROM mandi_prices
            WHERE crop_id = $1 AND mandi_id = $2 AND is_holiday = false
              AND date >= current_date - ($3 || ' days')::interval
            ORDER BY date ASC
            """,
            parsed.crop_id,
            parsed.mandi_id,
            str(days),
        )
        return success(
            {
                "crop_id": parsed.crop_id,
                "mandi_id": parsed.mandi_id,
                "range": parsed.range,
                "history": to_jsonable(rows or []),
            }
        )
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "required" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.get("/predictions")
async def get_predictions(request: Request, session: dict = Depends(require_session)):
    try:
        qp = request.query_params
        parsed = PredictionQuery.model_validate({"crop_id": qp.get("crop_id"), "mandi_id": qp.get("mandi_id")})
        rows = await query(
            """
            SELECT date, modal_price
            FROM mandi_prices
            WHERE crop_id = $1 AND mandi_id = $2 AND is_holiday = false
            ORDER BY date ASC
            """,
            parsed.crop_id,
            parsed.mandi_id,
        )
        check = can_forecast(rows or [])
        if not check["ok"]:
            return success(
                {
                    "crop_id": parsed.crop_id,
                    "mandi_id": parsed.mandi_id,
                    "can_forecast": False,
                    "reason": check["reason"],
                    "row_count": check["rowCount"],
                    "last_date": check["lastDate"],
                    "predictions": [],
                    "recommendation": "HOLD",
                    "recommendation_reason": "Not enough price data to generate a forecast.",
                    "volatility_warning": True,
                    "model_confidence": 0,
                }
            )
        forecast = forecast_prices(rows or [], 14)
        return success(
            {
                "crop_id": parsed.crop_id,
                "mandi_id": parsed.mandi_id,
                "can_forecast": True,
                **to_jsonable(forecast),
            }
        )
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "required" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.get("/health")
async def get_prices_health():
    sources = ["amis_pk", "samis_pk", "fmis_kp", "bmis_balochistan", "pbs_spi"]
    try:
        latest = await query(
            """
            SELECT DISTINCT ON (source_code) source_code, status, received_at, rows_written
            FROM scraper_runs
            ORDER BY source_code, received_at DESC
            """
        )
        by_source = {r.get("source_code"): r for r in (latest or [])}
        most_recent = None
        out_sources: dict[str, Any] = {}
        for code in sources:
            row = by_source.get(code)
            if row and row.get("received_at"):
                dt = row["received_at"]
                if most_recent is None or dt > most_recent:
                    most_recent = dt
            out_sources[code] = {
                "status": (row or {}).get("status", "no_data"),
                "last_success": row.get("received_at").isoformat() if row and row.get("received_at") else None,
                "rows": int((row or {}).get("rows_written") or 0),
            }
        last_run_age_hours = None
        if most_recent:
            last_run_age_hours = round((datetime.now(timezone.utc) - most_recent).total_seconds() / 3600, 1)
        return success(
            {
                "last_successful_run": most_recent.isoformat() if most_recent else None,
                "last_run_age_hours": last_run_age_hours,
                "sources": out_sources,
            }
        )
    except Exception:
        return success(
            {
                "last_successful_run": None,
                "last_run_age_hours": None,
                "sources": {s: {"status": "no_data", "last_success": None, "rows": 0} for s in sources},
            }
        )


@router.get("/alerts")
async def list_price_alerts(session: dict = Depends(require_session)):
    try:
        alerts = await query(
            """
            SELECT a.id, a.crop_id, c.name_en as crop_name_en,
                   a.mandi_id, m.name_en as mandi_name_en,
                   a.target_price_pkr, a.status, a.last_triggered_at
            FROM price_alerts a
            JOIN crops c ON c.id = a.crop_id
            LEFT JOIN mandis m ON m.id = a.mandi_id
            WHERE a.user_id = $1
            ORDER BY a.created_at DESC
            """,
            session["accountId"],
        )
        return success({"alerts": to_jsonable(alerts or [])})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/alerts")
async def create_price_alert(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = AlertCreateRequest.model_validate(body or {})

        crop = await query_one("SELECT id FROM crops WHERE id = $1", parsed.crop_id)
        if not crop:
            return error_response("not_found", "Crop not found", 404)
        if parsed.mandi_id:
            mandi = await query_one("SELECT id FROM mandis WHERE id = $1", parsed.mandi_id)
            if not mandi:
                return error_response("not_found", "Mandi not found", 404)

        alert = await query_one(
            """
            INSERT INTO price_alerts (user_id, crop_id, mandi_id, target_price_pkr, status)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, crop_id,
                      (SELECT name_en FROM crops WHERE id = $2) as crop_name_en,
                      mandi_id,
                      (SELECT name_en FROM mandis WHERE id = $3) as mandi_name_en,
                      target_price_pkr, status
            """,
            session["accountId"],
            parsed.crop_id,
            parsed.mandi_id,
            parsed.target_price_pkr,
            parsed.status,
        )
        return success({"alert": to_jsonable(alert)}, status_code=201)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.put("/alerts")
async def update_price_alert(request: Request, session: dict = Depends(require_session)):
    try:
        alert_id = request.query_params.get("id")
        if not alert_id:
            return error_response("validation_error", "Alert id is required", 422)
        body = await read_json_body(request)
        parsed = AlertUpdateRequest.model_validate(body or {})
        if parsed.target_price_pkr is None and parsed.status is None:
            return error_response("validation_error", "No fields to update", 422)

        existing = await query_one("SELECT user_id FROM price_alerts WHERE id = $1", alert_id)
        if not existing:
            return error_response("not_found", "Alert not found", 404)
        if str(existing.get("user_id")) != str(session["accountId"]):
            return error_response("unauthorized", "Forbidden", 403)

        alert = await query_one(
            """
            UPDATE price_alerts
            SET target_price_pkr = COALESCE($2, target_price_pkr),
                status = COALESCE($3, status),
                updated_at = now()
            WHERE id = $1
            RETURNING id, crop_id,
                      (SELECT name_en FROM crops WHERE id = price_alerts.crop_id) as crop_name_en,
                      mandi_id,
                      (SELECT name_en FROM mandis WHERE id = price_alerts.mandi_id) as mandi_name_en,
                      target_price_pkr, status
            """,
            alert_id,
            parsed.target_price_pkr,
            parsed.status,
        )
        return success({"alert": to_jsonable(alert)})
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower():
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.delete("/alerts")
async def delete_price_alert(request: Request, session: dict = Depends(require_session)):
    try:
        alert_id = request.query_params.get("id")
        if not alert_id:
            return error_response("validation_error", "Alert id is required", 422)
        existing = await query_one("SELECT user_id FROM price_alerts WHERE id = $1", alert_id)
        if not existing:
            return error_response("not_found", "Alert not found", 404)
        if str(existing.get("user_id")) != str(session["accountId"]):
            return error_response("unauthorized", "Forbidden", 403)
        await execute("DELETE FROM price_alerts WHERE id = $1", alert_id)
        return success({"success": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/ingest")
async def ingest_prices(request: Request):
    try:
        secret = os.getenv("PRICES_CRON_SECRET")
        if not secret:
            return error_response("server_error", "PRICES_CRON_SECRET is not configured on the server", 500)

        auth_header = request.headers.get("authorization")
        if auth_header != f"Bearer {secret}":
            return error_response("unauthorized", "Unauthorized", 401)

        ip = client_ip(request)
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        if not rate_limit.hit("prices-ingest:ip", ip, 10, 60_000, now_ms=now_ms):
            return error_response("rate_limited", "Too many requests", 429)

        body = await read_json_body(request)
        if not isinstance(body, dict):
            return error_response("validation_error", "Invalid JSON body", 400)

        source_code = body.get("source_code")
        rows = body.get("rows")
        allowed_sources = {"amis_pk", "samis_pk", "fmis_kp", "bmis_balochistan", "pbs_spi"}
        if source_code not in allowed_sources or not isinstance(rows, list) or len(rows) == 0:
            return error_response("validation_error", "Invalid ingest payload", 400)

        written = 0
        rejected = 0
        mandi_rows = await query("SELECT id, district FROM mandis")
        mandi_ids = {str(m.get("id")) for m in (mandi_rows or [])}
        crop_rows = await query("SELECT id FROM crops")
        crop_ids = {str(c.get("id")) for c in (crop_rows or [])}

        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                for row in rows:
                    if not isinstance(row, dict):
                        rejected += 1
                        continue
                    mandi_external_id = str(row.get("mandi_external_id") or "")
                    crop_external_id = str(row.get("crop_external_id") or "")
                    date_val = str(row.get("date") or "")
                    try:
                        modal_price = float(row.get("modal_price"))
                        min_price = float(row.get("min_price"))
                        max_price = float(row.get("max_price"))
                    except Exception:
                        rejected += 1
                        continue
                    if mandi_external_id not in mandi_ids or crop_external_id not in crop_ids:
                        rejected += 1
                        continue
                    try:
                        await conn.execute(
                            """
                            INSERT INTO mandi_prices
                              (mandi_id, crop_id, date, modal_price, min_price, max_price, unit, source, source_code, is_holiday)
                            VALUES ($1,$2,$3,$4,$5,$6,'Maund','govt_api',$7,$8)
                            ON CONFLICT (mandi_id, crop_id, date, source_code) DO UPDATE SET
                              modal_price = EXCLUDED.modal_price,
                              min_price = EXCLUDED.min_price,
                              max_price = EXCLUDED.max_price,
                              is_holiday = EXCLUDED.is_holiday,
                              source = EXCLUDED.source,
                              source_code = EXCLUDED.source_code
                            """,
                            mandi_external_id,
                            crop_external_id,
                            date_val,
                            modal_price,
                            min_price,
                            max_price,
                            source_code,
                            bool(row.get("is_holiday", False)),
                        )
                        written += 1
                    except Exception:
                        rejected += 1

        status = "partial" if rejected > 0 else "ok"
        try:
            await execute(
                "INSERT INTO scraper_runs (source_code, status, rows_written, rows_rejected, caller_ip) VALUES ($1,$2,$3,$4,$5)",
                source_code,
                status,
                written,
                rejected,
                ip,
            )
        except Exception:
            pass

        return success(
            {
                "success": True,
                "request_id": str(uuid4()),
                "rows_written": written,
                "rows_rejected": rejected,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "source_code": source_code,
                "alerts_evaluated": 0,
                "alerts_triggered": 0,
            }
        )
    except Exception as err:
        return error_response("server_error", str(err), 500)
