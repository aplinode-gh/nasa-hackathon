"""Scheduled task API routes."""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, Request

from app.core.http import error_response, success
from app.db.session import execute, query
from app.services.prices.forecast import forecast_prices

router = APIRouter(prefix="/cron", tags=["cron"])

CROP_LIMIT = 20


@router.post("/predict-prices")
async def predict_prices(request: Request):
    """Refresh cached 14-day price forecasts for active crops."""
    try:
        secret = os.getenv("CRON_SECRET")
        if not secret:
            return error_response("MISCONFIGURED", "CRON_SECRET not set", 500)

        auth = request.headers.get("authorization") or ""
        if auth != f"Bearer {secret}":
            return error_response("UNAUTHORIZED", "Invalid cron secret", 401)

        crops = await query(
            "SELECT id, name_en FROM crops ORDER BY name_en LIMIT $1",
            CROP_LIMIT,
        )
        if not crops:
            return success({"ok": True, "processed": 0})

        processed = 0
        errors: list[str] = []

        for crop in crops:
            try:
                # Use recent daily averages as model input.
                rows = await query(
                    """
                    SELECT date::text AS date,
                           ROUND(AVG(modal_price))::int AS modal_price
                    FROM mandi_prices
                    WHERE crop_id = $1
                      AND date >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY date
                    ORDER BY date
                    """,
                    crop["id"],
                )
                if not rows or len(rows) < 7:
                    continue

                result = forecast_prices(
                    [{"date": r["date"], "modal_price": float(r["modal_price"])} for r in rows],
                    14,
                )

                # Persist the latest forecast snapshot for quick reads.
                await execute(
                    """
                    INSERT INTO price_predictions
                      (crop_id, mandi_id, calculated_at, forecast_json,
                       recommendation, recommendation_reason, volatility_warning, model_confidence)
                    VALUES ($1, NULL, NOW(), $2::jsonb, $3, $4, $5, $6)
                    ON CONFLICT (crop_id) DO UPDATE SET
                      calculated_at = NOW(),
                      forecast_json = EXCLUDED.forecast_json,
                      recommendation = EXCLUDED.recommendation,
                      recommendation_reason = EXCLUDED.recommendation_reason,
                      volatility_warning = EXCLUDED.volatility_warning,
                      model_confidence = EXCLUDED.model_confidence
                    """,
                    crop["id"],
                    json.dumps(result["predictions"]),
                    result["recommendation"],
                    result["recommendation_reason"],
                    result["volatility_warning"],
                    result["model_confidence"],
                )
                processed += 1
            except Exception as e:
                errors.append(f"{crop.get('name_en', crop.get('id'))}: {e}")

        payload = {"ok": True, "processed": processed}
        if errors:
            payload["errors"] = errors
        return success(payload)
    except Exception as err:
        return error_response("server_error", str(err), 500)
