"""Weather forecast, advisory, and alert helpers."""

from __future__ import annotations

import base64
import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

import httpx

from app.db.session import query, query_one

CACHE_TTL_SECONDS = 30 * 60
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
HORIZON_DAYS = 7
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

CROP_DURATIONS = {
    "wheat": 120,
    "rice": 120,
    "cotton": 160,
    "maize": 100,
    "sugarcane": 330,
    "barley": 130,
    "mustard": 130,
    "sunflower": 110,
    "millet": 90,
    "sorghum": 110,
    "gram": 130,
    "lentil": 150,
    "potato": 110,
    "tomato": 120,
    "onion": 150,
}
DEFAULT_DURATION = 120

ADVICE_TEXT = {
    "app.weather.advisory.recommendation.irrigation": "Heavy rain expected. Delay irrigation and check field drainage.",
    "app.weather.advisory.recommendation.heatProtect": "High heat expected. Provide shade/water management and avoid midday stress.",
    "app.weather.advisory.recommendation.frostProtect": "Low temperature risk. Protect sensitive crops from frost.",
    "app.weather.advisory.recommendation.sprayDisease": "Warm and humid conditions increase disease risk. Monitor and spray only if needed.",
    "app.weather.advisory.recommendation.harvest": "Crop appears harvest-ready. Plan harvest around favorable weather windows.",
    "app.weather.advisory.recommendation.fertilize": "Flowering stage: follow recommended nutrient plan and monitor crop response.",
    "app.weather.advisory.recommendation.plantCare": "Maintain regular crop care and monitor field conditions.",
    "app.weather.advisory.recommendation.generic": "Monitor weather and field conditions, and plan activities accordingly.",
    "app.weather.alerts.heavyRain": "Heavy rain is expected soon. Delay field operations and protect drainage.",
    "app.weather.alerts.frost": "Frost risk detected. Take protective measures for sensitive crops.",
    "app.weather.alerts.extremeHeat": "Extreme heat expected. Increase monitoring and reduce crop stress where possible.",
    "app.weather.alerts.diseaseRisk": "Conditions favor crop disease. Inspect fields and act early if symptoms appear.",
}


def advice_text_for_key(key: str) -> str:
    return ADVICE_TEXT.get(key, key.replace("app.weather.", "").replace(".", " ").replace("_", " ").strip().capitalize())


def _days_between(from_date: str, to_date: str) -> int:
    try:
        a = datetime.fromisoformat(from_date.replace("Z", "+00:00")).date()
        b = datetime.fromisoformat(to_date.replace("Z", "+00:00")).date()
        return (b - a).days
    except Exception:
        return -1


def compute_growth_stage(primary_crop: str | None, sowing_date: str | None, ref_date: str) -> str:
    if not primary_crop or not sowing_date:
        return "generic"
    elapsed = _days_between(sowing_date, ref_date)
    if elapsed < 0:
        return "generic"
    duration = CROP_DURATIONS.get(primary_crop.lower(), DEFAULT_DURATION)
    frac = elapsed / duration if duration else 0
    if frac < 0.15:
        return "seedling"
    if frac < 0.45:
        return "vegetative"
    if frac < 0.7:
        return "flowering"
    if frac < 0.92:
        return "maturation"
    return "harvestReady"


def generate_day_advice(day: dict[str, Any], primary_crop: str | None, stage: str) -> tuple[str, str]:
    precip = float(day.get("precip_mm") or 0)
    temp_max = float(day.get("temp_max") or 0)
    temp_min = float(day.get("temp_min") or 0)
    humidity = float(day.get("humidity") or 0)

    if precip >= 10:
        return "app.weather.advisory.recommendation.irrigation", "warning"
    if temp_max > 40:
        return "app.weather.advisory.recommendation.heatProtect", "warning"
    if temp_min < 2:
        return "app.weather.advisory.recommendation.frostProtect", "warning"
    if humidity >= 80 and 20 <= temp_max <= 30:
        return "app.weather.advisory.recommendation.sprayDisease", "warning"
    if stage == "harvestReady":
        return "app.weather.advisory.recommendation.harvest", "info"
    if stage == "flowering":
        return "app.weather.advisory.recommendation.fertilize", "info"
    if primary_crop and stage != "generic":
        return "app.weather.advisory.recommendation.plantCare", "info"
    return "app.weather.advisory.recommendation.generic", "info"


def _cache_key(lat: float, lng: float) -> str:
    return f"{lat:.3f},{lng:.3f}"


def _pad_to_horizon(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not days:
        return days
    days = sorted(days, key=lambda d: d["date"])[:HORIZON_DAYS]
    if len(days) >= HORIZON_DAYS:
        return days
    last = days[-1]
    out = list(days)
    i = 1
    while len(out) < HORIZON_DAYS:
        try:
            next_date = (datetime.fromisoformat(last["date"]) + timedelta(days=i)).date().isoformat()
        except Exception:
            break
        out.append({**last, "date": next_date})
        i += 1
    return out


def _aggregate_days(hours: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, list[dict[str, Any]]] = {}
    for h in hours:
        day = str(h.get("time", ""))[:10]
        if not day:
            continue
        by_day.setdefault(day, []).append(h)

    days: list[dict[str, Any]] = []
    for date_str, steps in by_day.items():
        if not steps:
            continue
        temps = [float(s.get("temp_c", 0)) for s in steps]
        humidity_sum = sum(float(s.get("humidity", 0)) for s in steps)
        precip = sum(float(s.get("precip_mm", 0)) for s in steps)
        rep = max(steps, key=lambda s: float(s.get("precip_mm", 0)))
        days.append(
            {
                "date": date_str,
                "temp_max": round(max(temps)),
                "temp_min": round(min(temps)),
                "precip_mm": round(precip * 10) / 10,
                "humidity": round(humidity_sum / len(steps)),
                "description": rep.get("condition") or "Clear",
                "condition": rep.get("condition") or "Clear",
            }
        )
    days.sort(key=lambda d: d["date"])
    return _pad_to_horizon(days)


async def get_forecast(lat: float, lng: float) -> dict[str, Any] | None:
    key = _cache_key(lat, lng)
    now = datetime.now(timezone.utc).timestamp()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return None

    params = {"lat": lat, "lon": lng, "appid": api_key, "units": "metric"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(FORECAST_URL, params=params)
        if res.status_code != 200:
            return None
        data = res.json()
        items = data.get("list") or []
        if not items:
            return None
        hours = []
        for item in items:
            if not item.get("dt_txt"):
                continue
            weather0 = (item.get("weather") or [{}])[0]
            rain = ((item.get("rain") or {}).get("3h") or 0)
            snow = ((item.get("snow") or {}).get("3h") or 0)
            wind_mps = ((item.get("wind") or {}).get("speed") or 0)
            hours.append(
                {
                    "time": item["dt_txt"],
                    "temp_c": round(float(((item.get("main") or {}).get("temp") or 0))),
                    "rain_pct": round(float(item.get("pop") or 0) * 100),
                    "precip_mm": round(float(rain or snow) * 10) / 10,
                    "humidity": round(float(((item.get("main") or {}).get("humidity") or 0))),
                    "wind_kph": round(float(wind_mps) * 3.6),
                    "condition": weather0.get("main") or "Clear",
                }
            )
        result = {"days": _aggregate_days(hours), "hourly": hours, "source": "live"}
        _CACHE[key] = (now, result)
        return result
    except Exception:
        return None


def build_advisory_days(primary_crop: str | None, sowing_date: str | None, forecast: dict[str, Any]) -> list[dict[str, Any]]:
    days = []
    for day in forecast.get("days", []):
        stage = compute_growth_stage(primary_crop, sowing_date, day["date"])
        advice_key, severity = generate_day_advice(day, primary_crop, stage)
        days.append(
            {
                "date": day["date"],
                "weather": {
                    "temp_max": day.get("temp_max"),
                    "temp_min": day.get("temp_min"),
                    "precip_mm": day.get("precip_mm"),
                    "humidity": day.get("humidity"),
                    "description": day.get("description"),
                },
                "growth_stage": stage,
                "advice_key": advice_key,
                "advice_text": advice_text_for_key(advice_key),
                "severity": severity,
            }
        )
    return days


def scan_alert_conditions(forecast: dict[str, Any]) -> list[dict[str, Any]]:
    seen = set()
    found = []
    for step in (forecast.get("hourly") or [])[:8]:
        precip = float(step.get("precip_mm") or 0)
        temp = float(step.get("temp_c") or 0)
        humidity = float(step.get("humidity") or 0)
        if precip >= 10 and "heavy_rain" not in seen:
            seen.add("heavy_rain")
            found.append(
                {
                    "type": "heavy_rain",
                    "severity": "critical" if precip >= 20 else "warning",
                    "recommendation_key": "app.weather.alerts.heavyRain",
                    "condition_met": {"precip_mm": precip, "temp_c": temp},
                }
            )
        if temp < 2 and "frost" not in seen:
            seen.add("frost")
            found.append(
                {
                    "type": "frost",
                    "severity": "warning",
                    "recommendation_key": "app.weather.alerts.frost",
                    "condition_met": {"temp_c": temp},
                }
            )
        if temp > 40 and "extreme_heat" not in seen:
            seen.add("extreme_heat")
            found.append(
                {
                    "type": "extreme_heat",
                    "severity": "critical",
                    "recommendation_key": "app.weather.alerts.extremeHeat",
                    "condition_met": {"temp_c": temp},
                }
            )
        if humidity >= 80 and 20 <= temp <= 30 and "disease_risk" not in seen:
            seen.add("disease_risk")
            found.append(
                {
                    "type": "disease_risk",
                    "severity": "warning",
                    "recommendation_key": "app.weather.alerts.diseaseRisk",
                    "condition_met": {"humidity": humidity, "temp_c": temp},
                }
            )
    return found


def _send_alert_email(to: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    from_addr = os.getenv("EMAIL_FROM") or os.getenv("SMTP_FROM")
    if not host or not from_addr:
        return False
    port = int(os.getenv("SMTP_PORT") or 587)
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")
    try:
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception:
        return False


async def run_alert_scan(farm: dict[str, Any], forecast: dict[str, Any], account_email: str | None) -> list[dict[str, Any]]:
    conditions = scan_alert_conditions(forecast)
    if not conditions:
        return []

    created = []
    for condition in conditions:
        recent = await query_one(
            """
            SELECT id FROM weather_alerts
            WHERE farm_id = $1 AND alert_type = $2 AND created_at > now() - interval '6 hours'
            """,
            farm["farm_id"],
            condition["type"],
        )
        if recent:
            continue

        recommendation = advice_text_for_key(condition["recommendation_key"])
        row = await query_one(
            """
            INSERT INTO weather_alerts (
              farm_id, account_id, alert_type, condition_met,
              recommendation, recommendation_key, severity, sent_via
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            farm["farm_id"],
            farm["account_id"],
            condition["type"],
            json.dumps(condition["condition_met"]),
            recommendation,
            condition["recommendation_key"],
            condition["severity"],
            json.dumps(["in_app"]),
        )
        if not row:
            continue

        sent_via = ["in_app"]
        if account_email:
            subject = f"Weather alert - {condition['type'].replace('_', ' ')}"
            if _send_alert_email(account_email, subject, recommendation):
                sent_via = ["in_app", "email"]
                await query(
                    "UPDATE weather_alerts SET sent_via = $1, sent_at = now() WHERE id = $2",
                    json.dumps(sent_via),
                    row["id"],
                )
                row["sent_via"] = sent_via
                row["sent_at"] = datetime.now(timezone.utc)
        created.append(row)
    return created


def encode_cursor(advisory_date: str, advisory_id: str) -> str:
    raw = f"{advisory_date}__{advisory_id}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def decode_cursor(cursor: str | None) -> tuple[str | None, str | None]:
    if not cursor:
        return None, None
    try:
        raw = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
        date_str, item_id = raw.split("__", 1)
        return date_str, item_id
    except Exception:
        return None, None
