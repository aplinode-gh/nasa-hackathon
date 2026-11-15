"""Pest outbreak scoring, prediction storage, and alert generation."""

from __future__ import annotations

import asyncio
import json
import smtplib
from datetime import date
from email.message import EmailMessage
from typing import Any

from app.core.config import settings
from app.db.session import execute, query, query_one

AFFECTED_STAGE_POINTS = 25
AMBIENT_WEATHER_POINTS = 15
RISK_ACTIVE = 70
ESCALATION_WINDOW_HOURS = 6
RISK_THRESHOLD = 70

PEST_RULES: dict[str, dict[str, Any]] = {
    "aphid": {"weight": 1.0, "stages": ["Vegetative", "Tillering", "Panicle initiation"], "conditions": ["Clear", "Clouds"]},
    "jassid": {"weight": 0.95, "stages": ["Vegetative", "Tillering"], "conditions": ["Clear", "Clouds"]},
    "whitefly": {"weight": 1.05, "stages": ["Squaring", "Flowering", "Boll filling"], "conditions": ["Clear", "Clouds", "Mist"]},
    "bollworm": {"weight": 1.1, "stages": ["Squaring", "Flowering", "Boll filling"], "conditions": ["Clear", "Clouds"]},
    "armyworm": {"weight": 1.0, "stages": ["Vegetative", "Grain filling", "Tasselling"], "conditions": ["Clear", "Clouds", "Mist", "Rain"]},
    "rust": {"weight": 1.05, "stages": ["Vegetative", "Grain filling", "Panicle initiation"], "conditions": ["Rain", "Clouds", "Mist"]},
    "locust": {"weight": 1.0, "stages": ["Sowing", "Vegetative", "Grand growth"], "conditions": ["Clear", "Clouds"]},
}

STAGE_VULNERABILITY = {
    "sowing": 0.3,
    "tillering": 0.7,
    "vegetative": 0.9,
    "grain_filling": 0.8,
    "ready": 0.4,
    "squaring": 0.8,
    "flowering": 0.9,
    "boll_filling": 0.85,
    "grand_growth": 0.8,
    "ripening": 0.5,
    "harvest": 0.2,
    "panicle_initiation": 0.75,
    "tasselling": 0.8,
}

CONDITION_FAMILY = {
    "Thunderstorm": "Rain",
    "Squall": "Rain",
    "Tornado": "Rain",
    "Drizzle": "Rain",
    "Rain": "Rain",
    "Snow": "Rain",
    "Mist": "Mist",
    "Haze": "Mist",
    "Fog": "Mist",
    "Smoke": "Mist",
    "Dust": "Mist",
    "Sand": "Mist",
    "Ash": "Mist",
    "Clouds": "Clouds",
    "Clear": "Clear",
}


def _normalize_stage(stage: str) -> str:
    return (stage or "").replace(" ", "_").lower()


def _family(condition: str) -> str:
    return CONDITION_FAMILY.get(condition or "", "Clear")


def _weather_factor(day: dict[str, Any]) -> int:
    score = 0
    family = _family(str(day.get("condition") or ""))
    if family == "Rain":
        score += 15
    if float(day.get("precip_mm") or 0) > 5:
        score += 10
    if float(day.get("humidity") or 0) > 80:
        score += 10
    if float(day.get("humidity") or 0) > 60:
        score += 5
    if float(day.get("temp_max") or 0) > 35:
        score += 5
    return min(score, 30)


async def get_latest_incidence(province: str, district: str, crop: str) -> list[dict[str, Any]]:
    return await query(
        """
        SELECT pest_type, reported_count, district
        FROM pest_incidence_records
        WHERE province = $1 AND district = $2 AND crop = $3
          AND data_date >= current_date - 30
        ORDER BY data_date DESC LIMIT 20
        """,
        province,
        district,
        crop,
    ) or []


def _historical_factor(incidence: list[dict[str, Any]], pest: str) -> int:
    total = 0
    for row in incidence:
        if row.get("pest_type") == pest and int(row.get("reported_count") or 0) > 0:
            total += int(row.get("reported_count") or 0)
    return min(total, 25)


async def score_risk(
    input_data: dict[str, Any],
    incidence: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    stage_key = _normalize_stage(input_data["growth_stage"])
    stage_vuln = STAGE_VULNERABILITY.get(stage_key, 0.5)
    if incidence is None:
        incidence = await get_latest_incidence(input_data["province"], input_data["district"], input_data["crop"])

    results = []
    for day in input_data["forecast"]:
        if input_data["weather_source"] == "unavailable":
            results.append(
                {"date": day.get("date"), "riskScore": 0, "predictedPest": None, "confidence": 0, "status": "monitoring"}
            )
            continue

        family = _family(str(day.get("condition") or ""))
        weather = _weather_factor(day)
        best_pest = None
        best_score = 0
        second_best = 0

        for pest, rule in PEST_RULES.items():
            stage_matches = 1 if any(_normalize_stage(stage) == stage_key for stage in rule["stages"]) else 0
            weather_conducive = 1 if family in rule["conditions"] else 0
            raw = (
                stage_vuln * 35
                + stage_matches * AFFECTED_STAGE_POINTS
                + weather_conducive * AMBIENT_WEATHER_POINTS
                + weather
                + _historical_factor(incidence, pest)
            )
            weighted = round(raw * float(rule["weight"]))
            if weighted > best_score:
                second_best = best_score
                best_score = weighted
                best_pest = pest
            elif weighted > second_best:
                second_best = weighted

        risk_score = min(best_score, 100)
        confidence = min(100, max(15, round(45 + (best_score - second_best) * 2)))
        status = "active" if risk_score >= RISK_ACTIVE or confidence >= 60 else "monitoring"
        results.append(
            {
                "date": day.get("date"),
                "riskScore": risk_score,
                "predictedPest": best_pest if risk_score >= 20 else None,
                "confidence": confidence,
                "status": status,
            }
        )
    return results


async def store_predictions(input_data: dict[str, Any], results: list[dict[str, Any]]) -> None:
    by_date = {str(day.get("date")): day for day in input_data["forecast"]}
    for result in results:
        snapshot = by_date.get(str(result["date"]))
        await execute(
            """
            INSERT INTO pest_predictions
              (farm_id, account_id, prediction_date, risk_score, predicted_pest, confidence,
               model_version, weather_snapshot, farm_snapshot, province, district, status)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            ON CONFLICT (farm_id, prediction_date) DO UPDATE SET
              risk_score = EXCLUDED.risk_score,
              predicted_pest = EXCLUDED.predicted_pest,
              confidence = EXCLUDED.confidence,
              weather_snapshot = EXCLUDED.weather_snapshot,
              farm_snapshot = EXCLUDED.farm_snapshot,
              status = EXCLUDED.status,
              updated_at = now()
            """,
            input_data["farm_id"],
            input_data["account_id"],
            result["date"],
            result["riskScore"],
            result["predictedPest"],
            result["confidence"],
            "v1",
            json.dumps(snapshot or {}),
            json.dumps({"crop": input_data["crop"], "growthStage": input_data["growth_stage"]}),
            input_data["province"],
            input_data["district"],
            result["status"],
        )


async def _recommendation(pest: str, farm_name: str, crop: str) -> str:
    treatments = await query(
        "SELECT treatment_name, type, base_cost_pkr, unit FROM pest_treatments WHERE pest_type = $1 AND active = true",
        pest,
    )
    chemical = next((row for row in treatments or [] if row.get("type") == "chemical"), None)
    organic = next((row for row in treatments or [] if row.get("type") == "organic"), None)
    lines = [f"{pest.capitalize()} risk detected on {farm_name} ({crop})."]
    if chemical:
        lines.append(f"Chemical: {chemical['treatment_name']} — approx PKR {chemical['base_cost_pkr']}/{chemical['unit']}.")
    if organic:
        lines.append(f"Organic: {organic['treatment_name']} — approx PKR {organic['base_cost_pkr']}/{organic['unit']}.")
    lines.append("Consult your local agriculture office before applying.")
    return "\n".join(lines)


def _send_alert_email(to: str, subject: str, body: str) -> bool:
    if not (settings.smtp_host and settings.email_from):
        return False
    try:
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        port = int(settings.smtp_port or 587)
        if port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, port, timeout=10) as server:
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password or "")
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, port, timeout=10) as server:
                server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password or "")
                server.send_message(message)
        return True
    except Exception:
        return False


async def _create_alert(
    account_id: str,
    farm_id: str,
    pest: str,
    risk_score: int,
    farm_name: str,
    crop: str,
    escalation_of_id: str | None,
) -> dict[str, Any] | None:
    severity = "critical" if risk_score >= 85 else "warning"
    text = await _recommendation(pest, farm_name, crop)
    row = await query_one(
        """
        INSERT INTO pest_alerts
          (farm_id, account_id, pest_type, risk_score, severity, recommendation_text,
           recommendation_key, recommendation_translation_key, sent_via, escalation_of_id)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        RETURNING *
        """,
        farm_id,
        account_id,
        pest,
        risk_score,
        severity,
        text,
        f"app.pest.alerts.{pest}",
        f"app.pest.recommendations.{pest}",
        json.dumps(["in_app"]),
        escalation_of_id,
    )
    if not row:
        return None

    await execute(
        """
        INSERT INTO notifications (account_id, type, title, body, link_url)
        VALUES ($1, 'pest_alert', $2, $3, $4)
        """,
        account_id,
        f"{pest.capitalize()} — {risk_score}% risk",
        text,
        f"/pest/history/{row['id']}",
    )

    user = await query_one("SELECT email FROM users WHERE id = $1", account_id)
    email = (user or {}).get("email")
    if email and _send_alert_email(email, f"Pest alert: {pest} risk at {risk_score}%", text):
        await execute(
            "UPDATE pest_alerts SET sent_via = $1, sent_at = now() WHERE id = $2",
            json.dumps(["in_app", "email"]),
            row["id"],
        )
    return row


async def scan_and_alert(
    account_id: str,
    farm_id: str,
    farm_name: str,
    crop: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    created = []
    alerted: dict[str, dict[str, Any]] = {}
    existing = await query(
        f"""
        SELECT id, pest_type, risk_score, created_at FROM pest_alerts
        WHERE farm_id = $1 AND created_at > now() - interval '{ESCALATION_WINDOW_HOURS} hours'
        """,
        farm_id,
    )
    for row in existing or []:
        alerted[str(row["pest_type"])] = row

    for prediction in predictions:
        risk = int(prediction["riskScore"])
        pest = prediction.get("predictedPest")
        if risk < RISK_THRESHOLD or not pest:
            continue
        previous = alerted.get(pest)
        if previous:
            if risk > float(previous.get("risk_score") or 0):
                escalation = await _create_alert(account_id, farm_id, pest, risk, farm_name, crop, str(previous["id"]))
                if escalation:
                    created.append(escalation)
            continue
        alert = await _create_alert(account_id, farm_id, pest, risk, farm_name, crop, None)
        if alert:
            created.append(alert)
            alerted[pest] = alert
    return created


async def run_for_farm(farm: dict[str, Any]) -> dict[str, int]:
    crops = farm.get("crops")
    if isinstance(crops, str):
        try:
            crops = json.loads(crops)
        except Exception:
            crops = []
    crop = str((crops or ["wheat"])[0])
    stages = farm.get("growth_stages")
    if isinstance(stages, str):
        try:
            stages = json.loads(stages)
        except Exception:
            stages = {}
    growth_stage = str((stages or {}).get(crop) or "Sowing")

    from app.services.weather.service import get_forecast

    forecast = await get_forecast(float(farm["lat"]), float(farm["lng"]))
    today = date.today().isoformat()
    days = (forecast or {}).get("days") or [
        {"date": today, "condition": "Clear", "temp_max": 30, "temp_min": 20, "precip_mm": 0, "humidity": 50}
        for _ in range(7)
    ]

    input_data = {
        "farm_id": str(farm["id"]),
        "account_id": str(farm["account_id"]),
        "province": farm.get("province") or "Punjab",
        "district": farm.get("district") or "Unknown",
        "crop": crop,
        "growth_stage": growth_stage,
        "forecast": days,
        "weather_source": "live" if forecast else "unavailable",
    }
    results = await score_risk(input_data)
    await store_predictions(input_data, results)
    alerts = await scan_and_alert(
        input_data["account_id"], input_data["farm_id"], str(farm.get("name")), crop, results
    )
    return {"results": len(results), "alerts": len(alerts)}


async def run_all(concurrency: int = 4) -> dict[str, int]:
    farms = await query(
        "SELECT id, account_id, name, district, lat, lng, crops, growth_stages FROM farms WHERE archived_at IS NULL"
    )
    generated = 0
    alerted = 0
    failed = 0
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(farm: dict[str, Any]) -> None:
        nonlocal generated, alerted, failed
        async with semaphore:
            try:
                counts = await run_for_farm(farm)
                generated += counts["results"]
                alerted += counts["alerts"]
            except Exception:
                failed += 1

    await asyncio.gather(*(worker(farm) for farm in farms or []))
    return {"generated": generated, "alerted": alerted, "scraped": 0, "failed": failed}
