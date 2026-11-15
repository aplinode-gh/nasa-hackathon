"""Tool implementations used by the advisor agents."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.core.serialization import parse_json_field
from app.db.session import query, query_one
from app.services.ai.agent import Tool
from app.services.ai.llm import get_embedding_config
from app.services.crops.catalogue import get_compatibility_by_crop, get_crops_by_season_and_budget, resolve_soil_type
from app.services.crops.scoring import rank_candidates
from app.services.farms.weather import fetch_current_weather
from app.services.weather.service import get_forecast

STR = {"type": "string"}
OPT_STR = {"type": "string"}


def _fmt(value: Any, decimals: int = 0) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def _crop_list(value: Any) -> str:
    parsed = parse_json_field(value, value)
    if isinstance(parsed, list):
        return ", ".join(str(item) for item in parsed)
    return str(parsed or "")


def _stages(value: Any) -> str:
    parsed = parse_json_field(value, {})
    if isinstance(parsed, dict) and parsed:
        return ", ".join(f"{crop}: {stage}" for crop, stage in parsed.items())
    return "unknown"


async def _get_my_farms(account_id: str, args: dict[str, Any]) -> str:
    farm_name = (args.get("farmName") or "").strip().lower()
    sql = (
        "SELECT id, name, location, district, lat, lng, acres, crops, growth_stages, "
        "soil_type, irrigation_method, primary_crop, sowing_date FROM farms "
        "WHERE account_id = $1 AND archived_at IS NULL"
    )
    params: list[Any] = [account_id]
    if farm_name:
        sql += " AND lower(name) LIKE $2"
        params.append(f"%{farm_name}%")
    rows = await query(sql + " ORDER BY created_at DESC", *params)
    if not rows:
        return f"No farm found matching \"{farm_name}\"." if farm_name else "The farmer has no farms registered yet."

    lines = []
    for farm in rows:
        extra = f", soil: {farm['soil_type']}" if farm.get("soil_type") else ""
        extra += f", irrigation: {farm['irrigation_method']}" if farm.get("irrigation_method") else ""
        extra += f", sowed: {farm['sowing_date']}" if farm.get("sowing_date") else ""
        lines.append(
            f"• {farm['name']} ({farm.get('location')}, {farm.get('district')}): "
            f"{_fmt(farm.get('acres'))} acres, {_crop_list(farm.get('crops'))}, "
            f"stage: {_stages(farm.get('growth_stages'))}{extra}"
        )
    return "Farmer's farms:\n" + "\n".join(lines)


async def _get_my_records(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    record_type = args.get("recordType")
    conditions = ["r.account_id = $1"]
    params: list[Any] = [account_id]
    idx = 2

    if farm_id:
        owner = await query_one(
            "SELECT id FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL",
            farm_id,
            account_id,
        )
        if not owner:
            return "Farm not found or does not belong to you. Please check your farm list."
        conditions.append(f"r.farm_id = ${idx}")
        params.append(farm_id)
        idx += 1
    if record_type:
        conditions.append(f"r.type = ${idx}")
        params.append(record_type)
        idx += 1

    rows = await query(
        f"""
        SELECT r.id, r.farm_id, f.name AS farm_name, r.type, r.event_date, r.title,
               r.note, r.yield_qty, r.labor_cost, r.transport_cost
        FROM records r
        JOIN farms f ON f.id = r.farm_id AND f.account_id = $1
        WHERE {' AND '.join(conditions)}
        ORDER BY r.event_date DESC, r.created_at DESC
        LIMIT 50
        """,
        *params,
    )
    if not rows:
        return "No matching farm records found. The farmer may not have logged any activities yet."

    lines = []
    for row in rows:
        line = f"• [{row['farm_name']}] {row.get('title') or row['type']} ({row['type']}) — {row['event_date']}"
        if row.get("note"):
            line += f": {row['note']}"
        if row.get("yield_qty"):
            line += f" | Yield: {row['yield_qty']}"
        costs = []
        if row.get("labor_cost"):
            costs.append(f"labor Rs {_fmt(row['labor_cost'])}")
        if row.get("transport_cost"):
            costs.append(f"transport Rs {_fmt(row['transport_cost'])}")
        if costs:
            line += f" | Costs: {', '.join(costs)}"
        lines.append(line)
    return "Farm records:\n" + "\n".join(lines)


async def _get_farm_details(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    farm = await query_one(
        """
        SELECT f.*,
               COALESCE(
                 (SELECT jsonb_agg(jsonb_build_object(
                    'name', c.name_en, 'category', c.category,
                    'typical_yield_per_acre_kg', c.typical_yield_per_acre_kg,
                    'growing_duration_days', c.growing_duration_days,
                    'water_requirement_level', c.water_requirement_level,
                    'labour_cost_level', c.labour_cost_level,
                    'capital_requirement_per_acre_pkr', c.capital_requirement_per_acre_pkr,
                    'market_risk_baseline', c.market_risk_baseline
                 ))
                 FROM crops c
                 WHERE lower(c.name_en) = ANY(
                   SELECT lower(jsonb_array_elements_text(f.crops))
                 )), '[]'::jsonb
               ) AS crop_details
        FROM farms f
        WHERE f.id = $1 AND f.account_id = $2 AND f.archived_at IS NULL
        """,
        farm_id,
        account_id,
    )
    if not farm:
        return "Farm not found or does not belong to you."

    output = (
        f"Farm: {farm['name']}\nLocation: {farm.get('location')}, {farm.get('district')}\n"
        f"Size: {_fmt(farm.get('acres'))} acres\nSoil type: {farm.get('soil_type') or 'not recorded'}\n"
        f"Irrigation: {farm.get('irrigation_method') or 'not recorded'}\n"
        f"Primary crop: {farm.get('primary_crop') or 'not set'}\n"
        f"Sowing date: {farm.get('sowing_date') or 'not recorded'}\n"
        f"Crops: {_crop_list(farm.get('crops'))}\nGrowth stages: {_stages(farm.get('growth_stages'))}"
    )
    details = parse_json_field(farm.get("crop_details"), [])
    if isinstance(details, list) and details:
        lines = []
        for crop in details:
            lines.append(
                f"• {crop.get('name')} ({crop.get('category')}): yield ~{crop.get('typical_yield_per_acre_kg')} kg/acre, "
                f"duration {crop.get('growing_duration_days')} days, water: {crop.get('water_requirement_level')}, "
                f"labour: {crop.get('labour_cost_level')}, cost ~Rs {_fmt(crop.get('capital_requirement_per_acre_pkr'))}/acre, "
                f"market risk: {crop.get('market_risk_baseline')}"
            )
        output += "\n\nCrop details:\n" + "\n".join(lines)
    return output


async def _check_soil_crop_fit(account_id: str, args: dict[str, Any]) -> str:
    crop_name = args.get("cropName") or ""
    farm_id = args.get("farmId")
    soil_type = args.get("soilType")

    if farm_id and not soil_type:
        farm = await query_one(
            "SELECT soil_type FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL",
            farm_id,
            account_id,
        )
        if not farm:
            return "Farm not found or does not belong to you."
        soil_type = farm.get("soil_type")
    if not soil_type:
        return "No soil type available. Set the soil type on the farm, or provide one manually."

    rows = await query(
        """
        SELECT c.name_en AS crop_name, csc.soil_type, csc.suitability_score,
               csc.ph_min, csc.ph_max, csc.notes
        FROM crop_soil_compatibility csc
        JOIN crops c ON c.id = csc.crop_id
        WHERE lower(c.name_en) LIKE $1 AND csc.soil_type = $2
        LIMIT 5
        """,
        f"%{crop_name.lower()}%",
        soil_type,
    )
    if not rows:
        return f'No soil-crop compatibility data found for "{crop_name}" on {soil_type} soil.'

    lines = []
    for row in rows:
        score = float(row.get("suitability_score") or 0)
        label = "excellent" if score >= 0.9 else "good" if score >= 0.75 else "moderate" if score >= 0.5 else "poor"
        line = f"{row['crop_name']} on {row['soil_type']} soil: {label} fit (score {score:.2f})"
        if row.get("ph_min") and row.get("ph_max"):
            line += f", pH range {row['ph_min']}-{row['ph_max']}"
        if row.get("notes"):
            line += f"\n  Note: {row['notes']}"
        lines.append(line)
    return "\n\n".join(lines)


async def _get_my_weather_records(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    days = int(args.get("days") or 30)
    conditions = ["r.account_id = $1", "r.weather != '{}'::jsonb", "r.event_date >= current_date - $2::int"]
    params: list[Any] = [account_id, days]
    idx = 3
    if farm_id:
        conditions.append(f"r.farm_id = ${idx}")
        params.append(farm_id)
        idx += 1

    rows = await query(
        f"""
        SELECT f.name AS farm_name, r.event_date, r.type, r.title, r.weather
        FROM records r
        JOIN farms f ON f.id = r.farm_id AND f.account_id = $1
        WHERE {' AND '.join(conditions)}
        ORDER BY r.event_date DESC
        LIMIT 20
        """,
        *params,
    )
    if not rows:
        return f"No weather data found in farm records for the last {days} days."

    lines = []
    for row in rows:
        weather = parse_json_field(row.get("weather"), {}) or {}
        bits = []
        temp = weather.get("temp_c") or weather.get("temp") or weather.get("temperature")
        if temp is not None:
            bits.append(f"{temp}°C")
        if weather.get("humidity") is not None:
            bits.append(f"{weather['humidity']}% humidity")
        condition = weather.get("condition") or weather.get("weather") or weather.get("description")
        if condition:
            bits.append(str(condition))
        wind = weather.get("wind_kph") or weather.get("wind")
        if wind is not None:
            bits.append(f"wind {wind} km/h")
        line = f"• [{row['farm_name']}] {row.get('title') or row['type']} on {row['event_date']}"
        if bits:
            line += f"\n  Weather: {', '.join(bits)}"
        lines.append(line)
    return f"Weather conditions from farm activities (last {days} days):\n" + "\n".join(lines)


async def _get_my_farm_weather(account_id: str, args: dict[str, Any]) -> str:
    farm_name = (args.get("farmName") or "").strip().lower()
    sql = (
        "SELECT id, name, location, district, lat, lng, crops, growth_stages FROM farms "
        "WHERE account_id = $1 AND archived_at IS NULL"
    )
    params: list[Any] = [account_id]
    if farm_name:
        sql += " AND lower(name) LIKE $2"
        params.append(f"%{farm_name}%")
    farms = await query(sql + " ORDER BY created_at DESC", *params)
    if not farms:
        return "No farms registered. Add a farm first to get weather data."

    results = []
    for farm in farms:
        snapshot = await fetch_current_weather(float(farm["lat"]), float(farm["lng"]))
        if not snapshot.get("condition") and snapshot.get("temp_c") is None:
            results.append(f"• {farm['name']} ({farm.get('location')}): Weather data temporarily unavailable")
            continue
        parts = [f"• {farm['name']} ({farm.get('location')}) — {_crop_list(farm.get('crops'))}, {_stages(farm.get('growth_stages'))}:"]
        if snapshot.get("temp_c") is not None:
            parts.append(f"  {snapshot['temp_c']}°C")
        if snapshot.get("condition"):
            parts.append(f"  {snapshot['condition']}")
        if snapshot.get("humidity") is not None:
            parts.append(f"  {snapshot['humidity']}% humidity")
        if snapshot.get("wind_kph") is not None:
            parts.append(f"  wind {snapshot['wind_kph']} km/h")
        temp = snapshot.get("temp_c")
        humidity = snapshot.get("humidity")
        if temp is not None and humidity is not None:
            if temp > 38:
                parts.append("  ⚠ Heat stress risk — ensure irrigation")
            if temp < 5:
                parts.append("  ⚠ Frost risk — protect young crops")
            if humidity > 80 and temp > 20:
                parts.append("  ⚠ High humidity — fungal disease risk")
        if "rain" in str(snapshot.get("condition") or "").lower():
            parts.append("  ⚠ Rain — delay sprays")
        results.append("\n".join(parts))
    return "Current weather at your farms:\n" + "\n".join(results)


async def _get_weather(args: dict[str, Any]) -> str:
    lat = float(args["lat"])
    lng = float(args["lng"])
    label = args.get("locationName") or f"{lat:.2f}, {lng:.2f}"
    snapshot = await fetch_current_weather(lat, lng)
    if not snapshot.get("condition") and snapshot.get("temp_c") is None:
        return f"Weather data is currently unavailable for {label}."

    lines = [f"Current weather for {label}:"]
    if snapshot.get("temp_c") is not None:
        lines.append(f"Temperature: {snapshot['temp_c']}°C")
    if snapshot.get("condition"):
        lines.append(f"Conditions: {snapshot['condition']}")
    if snapshot.get("humidity") is not None:
        lines.append(f"Humidity: {snapshot['humidity']}%")

    temp = snapshot.get("temp_c")
    humidity = snapshot.get("humidity")
    if temp is not None and humidity is not None:
        if temp > 30 and humidity > 70:
            lines.append("⚠ High temperature + high humidity = elevated fungal disease risk. Scout crops closely.")
        if temp > 38:
            lines.append("⚠ Heat stress alert: ensure adequate irrigation.")
        if temp < 5:
            lines.append("⚠ Frost risk: protect young crops and vegetables.")
        if humidity > 80 and 20 < temp < 35:
            lines.append("High humidity favors whitefly, aphids, and fungal diseases. Monitor pest levels.")
    if "rain" in str(snapshot.get("condition") or "").lower():
        lines.append("Rain detected — delay planned sprays.")
    return "\n".join(lines)


async def _get_weather_forecast(args: dict[str, Any]) -> str:
    lat = float(args["lat"])
    lng = float(args["lng"])
    label = args.get("locationName") or f"{lat:.2f}, {lng:.2f}"
    forecast = await get_forecast(lat, lng)
    if not forecast or not forecast.get("days"):
        return f"Weather forecast is currently unavailable for {label}."

    lines = [f"7-day weather forecast for {label}:", ""]
    for day in forecast["days"]:
        lines.append(
            f"**{day.get('date')}**: {day.get('temp_min')}°C - {day.get('temp_max')}°C, {day.get('condition')}"
        )
        if float(day.get("precip_mm") or 0) > 0:
            lines.append(f"  Rainfall: {day.get('precip_mm')}mm")
        lines.append(f"  Humidity: {day.get('humidity')}%")

    today = (forecast.get("days") or [{}])[0]
    lines.extend(["", "## Farming interpretations:"])
    if float(today.get("temp_max") or 0) > 40:
        lines.append("- Extreme heat expected today — irrigate early morning or late evening.")
    if float(today.get("temp_min") or 0) < 5:
        lines.append("- Frost risk tonight — irrigate before sunset and cover young crops.")
    if float(today.get("precip_mm") or 0) > 10:
        lines.append("- Heavy rain expected — delay irrigation and spraying; clear drainage.")
    if float(today.get("humidity") or 0) > 80 and 20 < float(today.get("temp_min") or 0):
        lines.append("- High humidity — elevated fungal disease risk. Scout crops.")
    rain_days = [d.get("date") for d in forecast["days"][1:4] if float(d.get("precip_mm") or 0) > 5]
    if rain_days:
        lines.append(f"- Rain expected on {', '.join(str(d) for d in rain_days)} — plan spraying and irrigation around these days.")
    return "\n".join(lines)


async def _get_market_prices(args: dict[str, Any]) -> str:
    crop = args.get("crop")
    market = args.get("market")
    rows = await query(
        """
        SELECT DISTINCT ON (p.crop_id, p.mandi_id)
               c.name_en AS crop_name, m.name_en AS mandi_name,
               p.modal_price, p.min_price, p.max_price, p.date
        FROM mandi_prices p
        JOIN crops c ON c.id = p.crop_id
        JOIN mandis m ON m.id = p.mandi_id
        WHERE ($1::text IS NULL OR c.name_en ILIKE '%' || $1 || '%')
          AND ($2::text IS NULL OR m.name_en ILIKE '%' || $2 || '%')
        ORDER BY p.crop_id, p.mandi_id, p.date DESC
        LIMIT 20
        """,
        crop,
        market,
    )
    if not rows:
        return f"No current mandi price data found{(' for ' + crop) if crop else ''}{(' at ' + market) if market else ''}."

    lines = [
        f"• {row['crop_name']} at {row['mandi_name']}: Rs {_fmt(row['modal_price'])}/maund "
        f"(range Rs {_fmt(row['min_price'])}-{_fmt(row['max_price'])}, dated {row['date']})"
        for row in rows
    ]
    return "Current mandi prices:\n" + "\n".join(lines) + "\n\nPrices are indicative and may vary at the actual mandi."


async def _get_my_seasons(account_id: str, args: dict[str, Any]) -> str:
    status = args.get("status")
    farm_id = args.get("farmId")
    conditions = ["s.account_id = $1", "f.account_id = $1"]
    params: list[Any] = [account_id]
    idx = 2
    if status:
        conditions.append(f"s.status = ${idx}")
        params.append(status)
        idx += 1
    if farm_id:
        conditions.append(f"s.farm_id = ${idx}")
        params.append(farm_id)
        idx += 1

    rows = await query(
        f"""
        SELECT s.id, s.season, s.year, s.acres, s.status, s.expected_yield, s.expected_price,
               s.actual_yield, s.actual_price, f.name AS farm_name, c.name_en AS crop_name
        FROM seasons s
        JOIN farms f ON f.id = s.farm_id
        JOIN crops c ON c.id = s.crop_id
        WHERE {' AND '.join(conditions)}
        ORDER BY s.created_at DESC LIMIT 20
        """,
        *params,
    )
    if not rows:
        return "No seasons found. The farmer can create one from the Profit/Loss section."

    lines = []
    for row in rows:
        if row.get("actual_yield"):
            yield_info = f"harvest: {row['actual_yield']} units @ Rs {_fmt(row['actual_price'])}/unit"
        elif row.get("expected_yield"):
            yield_info = f"expected: {row['expected_yield']} units @ Rs {_fmt(row['expected_price'])}/unit"
        else:
            yield_info = "no yield data yet"
        lines.append(
            f"• {row['crop_name']} on {row['farm_name']} ({row['season']} {row['year']}): "
            f"{_fmt(row['acres'])} acres, {row['status']}, {yield_info}"
        )
    return "\n".join(lines)


async def _season_owner(season_id: str, account_id: str) -> dict[str, Any] | None:
    return await query_one(
        """
        SELECT s.*, f.name AS farm_name, c.name_en AS crop_name
        FROM seasons s
        JOIN farms f ON f.id = s.farm_id
        JOIN crops c ON c.id = s.crop_id
        WHERE s.id = $1 AND s.account_id = $2
        """,
        season_id,
        account_id,
    )


async def _get_season_expenses(account_id: str, args: dict[str, Any]) -> str:
    season = await _season_owner(args.get("seasonId"), account_id)
    if not season:
        return "Season not found or does not belong to you."

    expenses = await query(
        """
        SELECT e.category, e.amount, e.date, e.note, pc.total_projected_pkr AS projected_pkr
        FROM expenses e
        LEFT JOIN projected_costs pc ON pc.season_id = e.season_id AND pc.category = e.category
        WHERE e.season_id = $1
        ORDER BY e.date DESC, e.created_at DESC
        """,
        season["id"],
    )
    projected = await query(
        "SELECT category, per_acre_cost_pkr, total_projected_pkr FROM projected_costs WHERE season_id = $1",
        season["id"],
    )
    total_actual = sum(float(row.get("amount") or 0) for row in expenses)
    total_projected = sum(float(row.get("total_projected_pkr") or 0) for row in projected)

    output = [
        f"{season['crop_name']} on {season['farm_name']} ({season['season']} {season['year']}, {_fmt(season['acres'])} acres)",
        f"Status: {season['status']}",
        "",
    ]
    if projected:
        output.append("Projected costs (CACP baseline):")
        for row in projected:
            output.append(
                f"• {row['category']}: Rs {_fmt(row['per_acre_cost_pkr'])}/acre × {_fmt(season['acres'])} acres "
                f"= Rs {_fmt(row['total_projected_pkr'])}"
            )
        output.append(f"Total projected: Rs {_fmt(total_projected)}\n")
    else:
        output.append("No projected costs set for this season.\n")

    output.append("Actual expenses:")
    if not expenses:
        output.append("No expenses logged yet.")
    else:
        for row in expenses:
            line = f"• {row['category']} — Rs {_fmt(row['amount'])} on {row['date']}"
            if row.get("projected_pkr"):
                line += f" (vs projected Rs {_fmt(row['projected_pkr'])}, {'over' if float(row['amount']) > float(row['projected_pkr']) else 'under'} budget)"
            if row.get("note"):
                line += f" ({row['note']})"
            output.append(line)
        variance = total_actual - total_projected
        pct = (variance / total_projected * 100) if total_projected > 0 else 0
        output.append(f"Total actual: Rs {_fmt(total_actual)}")
        output.append(f"Variance: Rs {_fmt(abs(variance))} ({'over' if variance > 0 else 'under'} budget, {pct:.1f}%)")
    return "\n".join(output)


async def _get_profit_loss_summary(account_id: str, args: dict[str, Any]) -> str:
    season = await _season_owner(args.get("seasonId"), account_id)
    if not season:
        return "Season not found or does not belong to you."

    actual_row = await query_one(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE season_id = $1",
        season["id"],
    )
    projected_row = await query_one(
        "SELECT COALESCE(SUM(total_projected_pkr), 0) AS total FROM projected_costs WHERE season_id = $1",
        season["id"],
    )
    investment = float((actual_row or {}).get("total") or 0)
    projected_investment = float((projected_row or {}).get("total") or 0)

    expected_yield = float(season["expected_yield"]) if season.get("expected_yield") is not None else None
    expected_price = float(season["expected_price"]) if season.get("expected_price") is not None else None
    actual_yield = float(season["actual_yield"]) if season.get("actual_yield") is not None else None
    actual_price = float(season["actual_price"]) if season.get("actual_price") is not None else None

    projected_revenue = expected_yield * expected_price if expected_yield and expected_price else None
    actual_revenue = actual_yield * actual_price if actual_yield and actual_price else None
    net = actual_revenue - investment if actual_revenue is not None else None
    roi = (net / investment * 100) if investment > 0 and net is not None else None

    output = [
        f"{season['crop_name']} — {season['farm_name']} ({season['season']} {season['year']})",
        f"Area: {_fmt(season['acres'])} acres | Status: {season['status']}",
        "",
        "Investment:",
        f"• Total actual cost: Rs {_fmt(investment)}",
    ]
    if projected_investment > 0:
        output.append(f"• Total projected cost: Rs {_fmt(projected_investment)}")
        variance = investment - projected_investment
        output.append(f"• Variance: Rs {_fmt(abs(variance))} ({'over' if variance > 0 else 'under'} budget)")

    output.append("\nRevenue:")
    if actual_revenue is not None:
        output.append(f"• Actual revenue: Rs {_fmt(actual_revenue)} ({actual_yield} units × Rs {_fmt(actual_price)}/unit)")
    if projected_revenue is not None:
        output.append(f"• Projected revenue: Rs {_fmt(projected_revenue)} ({expected_yield} units × Rs {_fmt(expected_price)}/unit)")
    if actual_revenue is None and projected_revenue is None:
        output.append("• No yield/price data recorded yet.")

    output.append("\nProfit/Loss:")
    if net is not None:
        output.append(f"• {'Net Profit' if net >= 0 else 'Net Loss'}: Rs {_fmt(abs(net))}")
    elif projected_revenue is not None:
        projected_profit = projected_revenue - investment
        output.append(f"• {'Projected Profit' if projected_profit >= 0 else 'Projected Loss'}: Rs {_fmt(abs(projected_profit))}")
    else:
        output.append("• Add yield and price data to calculate profit/loss.")
    if roi is not None:
        output.append(f"• ROI: {roi:+.1f}%")

    if actual_price:
        output.append(f"\nBreak-even:\n• Need to produce: {investment / actual_price:.1f} units total to recover costs")
    if expected_yield:
        output.append(f"• Minimum price needed: Rs {investment / expected_yield:.0f}/unit to break even")
    return "\n".join(output)


async def _get_my_crop_recommendations(account_id: str, args: dict[str, Any]) -> str:
    conditions = ["r.account_id = $1"]
    params: list[Any] = [account_id]
    idx = 2
    for field, value in (("farm_id", args.get("farmId")), ("target_season", args.get("targetSeason")), ("target_year", args.get("targetYear"))):
        if value:
            conditions.append(f"r.{field} = ${idx}")
            params.append(value)
            idx += 1

    requests = await query(
        f"""
        SELECT r.*, f.name AS farm_name
        FROM crop_recommendation_requests r
        JOIN farms f ON f.id = r.farm_id
        WHERE {' AND '.join(conditions)}
        ORDER BY r.created_at DESC LIMIT 10
        """,
        *params,
    )
    if not requests:
        return "No crop recommendations found. The farmer can get recommendations from the Crops section."

    output = []
    for req in requests:
        recs = await query(
            """
            SELECT r.*, c.name_en, c.category
            FROM crop_recommendations r
            JOIN crops c ON c.id = r.crop_id
            WHERE r.request_id = $1
            ORDER BY r.rank ASC
            """,
            req["id"],
        )
        if not recs:
            continue
        top = recs[0]
        risk = parse_json_field(top.get("risk_factors"), [])
        output.append(f"{req['farm_name']} — {req['target_season']} {req['target_year']}:")
        output.append(f"  Top recommendation: {top['name_en']} (Rank {top['rank']})")
        output.append(
            f"  Suitability: {float(top['suitability_score']) * 100:.0f}% | "
            f"Profitability: {float(top['profitability_score']) * 100:.0f}% | "
            f"Final score: {float(top['final_score']) * 100:.0f}%"
        )
        output.append(f"  Expected revenue: Rs {_fmt(top['expected_revenue_per_acre_pkr'])}/acre")
        output.append(f"  Risk factors: {', '.join(risk) if isinstance(risk, list) and risk else 'none specified'}")
        if len(recs) > 1:
            output.append("  Alternatives: " + ", ".join(f"{r['name_en']} (score {float(r['final_score']) * 100:.0f}%)" for r in recs[1:]))
        output.append("")
    return "\n".join(output) if output else "Recommendation requests found but no crop suggestions available yet."


async def _get_farm_plan(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    conditions = ["fpe.account_id = $1"]
    params: list[Any] = [account_id]
    if farm_id:
        conditions.append("fpe.farm_id = $2")
        params.append(farm_id)

    plans = await query(
        f"""
        SELECT fpe.*, f.name AS farm_name
        FROM farm_plan_entries fpe
        JOIN farms f ON f.id = fpe.farm_id
        WHERE {' AND '.join(conditions)}
        ORDER BY fpe.created_at DESC LIMIT 10
        """,
        *params,
    )
    if not plans:
        return "No farm plan entries found. The farmer hasn't saved any crop plans yet."

    output = []
    for plan in plans:
        rotations = await query(
            """
            SELECT c.name_en AS crop_name, cs.reason_key, cs.sequence_position, cs.target_season, cs.target_year
            FROM crop_rotation_suggestions cs
            JOIN crops c ON c.id = cs.crop_id
            WHERE cs.farm_plan_entry_id = $1
            ORDER BY cs.sequence_position ASC
            """,
            plan["id"],
        )
        output.append(f"{plan['farm_name']} — {plan['target_season']} {plan['target_year']}:")
        if rotations:
            for index, row in enumerate(rotations, start=1):
                output.append(f"  {index}. {row['crop_name']} ({row['target_season']} {row['target_year']})")
        else:
            output.append("  Plan saved — no rotation details available")
        output.append("")
    return "\n".join(output)


async def _get_crop_candidates(account_id: str, args: dict[str, Any]) -> str:
    farm = await query_one(
        "SELECT * FROM farms WHERE id = $1 AND account_id = $2",
        args.get("farmId"),
        account_id,
    )
    if not farm:
        return "Farm not found."

    lat = float(farm["lat"])
    lng = float(farm["lng"])
    if not (23.5 <= lat <= 37.0 and 60.5 <= lng <= 77.0):
        return "Farm coordinates are outside Pakistan."

    season = str(args.get("season") or "winter").lower()
    budget = str(args.get("budgetBracket") or "medium")
    irrigation = str(args.get("irrigationType") or "canal")
    soil = await resolve_soil_type(str(args.get("soilType") or "other"), str(farm.get("district") or ""))

    forecast = await get_forecast(lat, lng)
    weather_available = bool(forecast and forecast.get("days"))

    price_rows = await query(
        "SELECT crop_id, price_per_maan_pkr, trend, volatility, observed_at FROM crop_price_trends ORDER BY crop_id, observed_at DESC"
    )
    latest: dict[str, dict[str, Any]] = {}
    for row in price_rows or []:
        latest.setdefault(str(row["crop_id"]), row)

    catalogue = await get_crops_by_season_and_budget(season, budget)
    if not catalogue:
        return f"No crops match the {season} season and {budget} budget bracket."

    compatibility = await get_compatibility_by_crop(soil["soilType"])
    past = await query_one(
        """
        SELECT c.category FROM farms f JOIN crops c ON lower(c.name_en) = lower(f.primary_crop)
        WHERE f.id = $1 LIMIT 1
        """,
        args.get("farmId"),
    )
    ctx = {
        "soilType": soil["soilType"],
        "season": season,
        "budget": budget,
        "irrigation": irrigation,
        "weatherAvailable": weather_available,
        "marketAvailable": bool(latest),
        "soilConfidence": "full" if soil.get("note") == "exact" else "degraded",
        "compatibilityByCrop": compatibility,
        "priceByCrop": {
            crop_id: {
                "pricePerMaanPkr": float(row.get("price_per_maan_pkr") or 0),
                "trend": row.get("trend") or "stable",
                "volatility": float(row.get("volatility") or 0),
            }
            for crop_id, row in latest.items()
        },
        "lastCropCategory": (past or {}).get("category"),
    }

    ranked = rank_candidates(catalogue, ctx, 3)
    lines = [
        f"Top 3 crop recommendations for {farm['name']} ({farm.get('location')}, {farm.get('district')}):",
        f"Season: {season} {args.get('year')} | Soil: {soil['soilType']} | Irrigation: {irrigation} | Budget: {budget}",
        "",
    ]
    for index, item in enumerate(ranked, start=1):
        crop = item["crop"]
        lines.append(f"**#{index} {crop['nameEn']}** ({crop['category']})")
        lines.append(f"  Final score: {item['scores']['final'] * 100:.1f}%")
        lines.append(f"  Expected revenue: PKR {_fmt(item['expectedRevenuePerAcrePkr'])}/acre ({item['revenueConfidence']} confidence)")
        lines.append(
            f"  Scores: suitability {item['scores']['suitability'] * 100:.0f}%, "
            f"weather {item['scores']['weatherFit'] * 100:.0f}%, "
            f"profit {item['scores']['profitability'] * 100:.0f}%, "
            f"risk {item['scores']['risk'] * 100:.0f}%, "
            f"sustainability {item['scores']['sustainability'] * 100:.0f}%"
        )
        lines.append(f"  Growing duration: {crop['growingDurationDays']} days")
        lines.append(f"  Water requirement: {crop['waterRequirementLevel']}")
        lines.append(f"  Capital needed: PKR {_fmt(crop['capitalRequirementPerAcrePkr'])}/acre")
        if item["riskFactors"]:
            lines.append(f"  Risk factors: {', '.join(item['riskFactors'])}")
        lines.append("")
    return "\n".join(lines)


async def _search_knowledge_base(args: dict[str, Any]) -> str:
    search_query = args.get("query") or ""
    crop_type = args.get("cropType")
    category = args.get("category")

    rows: list[dict[str, Any]] = []
    embedding = get_embedding_config()
    if embedding.api_key or "localhost" in embedding.base_url or "127.0.0.1" in embedding.base_url:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{embedding.base_url}/embeddings",
                    headers=embedding.headers,
                    json={"model": embedding.model, "input": search_query},
                )
                response.raise_for_status()
                vector_data = response.json()["data"][0]["embedding"]
            vector = "[" + ",".join(str(value) for value in vector_data) + "]"
            rows = await query(
                "SELECT * FROM advisor_search_similar($1::vector, $2, $3)",
                vector,
                5,
                0.35,
            )
        except Exception:
            rows = []

    if not rows:
        like = f"%{search_query}%"
        conditions = ["ch.content ILIKE $1"]
        params: list[Any] = [like]
        idx = 2
        if crop_type:
            conditions.append(f"d.crop_type = ${idx}")
            params.append(crop_type)
            idx += 1
        if category:
            conditions.append(f"d.category = ${idx}")
            params.append(category)
            idx += 1
        rows = await query(
            f"""
            SELECT ch.content, d.title AS document_title, d.crop_type, d.category, d.source
            FROM advisor_knowledge_chunks ch
            JOIN advisor_knowledge_documents d ON d.id = ch.document_id
            WHERE {' AND '.join(conditions)}
            LIMIT 5
            """,
            *params,
        )

    if not rows:
        return "No relevant information found in the knowledge base for this query. Suggest consulting a local extension officer."

    blocks = []
    for row in rows:
        header = f"## {row.get('document_title')}"
        if row.get("source"):
            header += f" (Source: {row['source']})"
        blocks.append(f"{header}\n{row.get('content')}")
    return "Knowledge base results (use ONLY this information for your response):\n\n" + "\n\n---\n\n".join(blocks)


async def _search_past_conversations(account_id: str, args: dict[str, Any]) -> str:
    term = args.get("query") or ""
    rows = await query(
        """
        SELECT title, summary, updated_at FROM advisor_conversations
        WHERE account_id = $1 AND summary IS NOT NULL AND summary ILIKE $2
        ORDER BY updated_at DESC LIMIT 5
        """,
        account_id,
        f"%{term}%",
    )
    if not rows:
        return f'No past conversations found matching "{term}".'
    lines = [f'• "{row["title"]}" ({str(row["updated_at"])[:10]}): {row["summary"]}' for row in rows]
    return "Past conversations:\n" + "\n".join(lines)


def build_advisor_tools(account_id: str) -> dict[str, Tool]:
    """Build the advisor tool registry bound to one account."""

    def account_tool(name: str, description: str, parameters: dict[str, Any], handler) -> Tool:
        async def bound(args: dict[str, Any]) -> str:
            return await handler(account_id, args)

        return Tool(name=name, description=description, parameters=parameters, handler=bound)

    def plain_tool(name: str, description: str, parameters: dict[str, Any], handler) -> Tool:
        return Tool(name=name, description=description, parameters=parameters, handler=handler)

    tools = [
        account_tool(
            "get_my_farms",
            "Get the farmer's registered farms with location, size, crops, growth stage, soil, and irrigation.",
            {"type": "object", "properties": {"farmName": OPT_STR}},
            _get_my_farms,
        ),
        account_tool(
            "get_my_records",
            "Get farm activity records (irrigation, fertilizer, pesticide, disease, harvest).",
            {
                "type": "object",
                "properties": {
                    "farmId": OPT_STR,
                    "recordType": {
                        "type": "string",
                        "enum": ["sowing", "planting", "irrigation", "fertilizer", "pesticide", "disease", "harvest"],
                    },
                },
            },
            _get_my_records,
        ),
        account_tool(
            "get_farm_details",
            "Get a farm profile including soil, irrigation, crop details, stages, and sowing date.",
            {"type": "object", "properties": {"farmId": STR}, "required": ["farmId"]},
            _get_farm_details,
        ),
        account_tool(
            "check_soil_crop_fit",
            "Check how well a crop suits the farm's soil with suitability score and pH range.",
            {
                "type": "object",
                "properties": {"cropName": STR, "farmId": OPT_STR, "soilType": OPT_STR},
                "required": ["cropName"],
            },
            _check_soil_crop_fit,
        ),
        account_tool(
            "get_my_weather_records",
            "Get weather recorded at the time of past farm activities.",
            {"type": "object", "properties": {"farmId": OPT_STR, "days": {"type": "number"}}},
            _get_my_weather_records,
        ),
        account_tool(
            "get_my_farm_weather",
            "Get live current weather at the farmer's own farm coordinates.",
            {"type": "object", "properties": {"farmName": OPT_STR}},
            _get_my_farm_weather,
        ),
        plain_tool(
            "get_weather",
            "Get current weather for any location in Pakistan using lat/lng.",
            {
                "type": "object",
                "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}, "locationName": OPT_STR},
                "required": ["lat", "lng"],
            },
            _get_weather,
        ),
        plain_tool(
            "get_weather_forecast",
            "Get the 7-day weather forecast for any location in Pakistan.",
            {
                "type": "object",
                "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}, "locationName": OPT_STR},
                "required": ["lat", "lng"],
            },
            _get_weather_forecast,
        ),
        plain_tool(
            "get_market_prices",
            "Get current mandi prices per maund with min-max range and date.",
            {"type": "object", "properties": {"crop": OPT_STR, "market": OPT_STR}},
            _get_market_prices,
        ),
        account_tool(
            "get_my_seasons",
            "Get the farmer's seasons with crop, farm, acres, status, yield, and price data.",
            {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["active", "harvested", "completed"]},
                    "farmId": OPT_STR,
                },
            },
            _get_my_seasons,
        ),
        account_tool(
            "get_season_expenses",
            "Get expenses and projected costs for a season.",
            {"type": "object", "properties": {"seasonId": STR}, "required": ["seasonId"]},
            _get_season_expenses,
        ),
        account_tool(
            "get_profit_loss_summary",
            "Get investment, revenue, net profit/loss, ROI, and break-even for a season.",
            {"type": "object", "properties": {"seasonId": STR}, "required": ["seasonId"]},
            _get_profit_loss_summary,
        ),
        account_tool(
            "get_my_crop_recommendations",
            "Get past crop recommendation results with scores, revenue, and risks.",
            {
                "type": "object",
                "properties": {"farmId": OPT_STR, "targetSeason": OPT_STR, "targetYear": OPT_STR},
            },
            _get_my_crop_recommendations,
        ),
        account_tool(
            "get_farm_plan",
            "Get saved farm plans with crop rotation suggestions.",
            {"type": "object", "properties": {"farmId": OPT_STR}},
            _get_farm_plan,
        ),
        account_tool(
            "get_crop_candidates",
            "Get the top 3 scored crop candidates for a farm, season, soil, irrigation, and budget.",
            {
                "type": "object",
                "properties": {
                    "farmId": STR,
                    "soilType": STR,
                    "irrigationType": STR,
                    "budgetBracket": STR,
                    "season": STR,
                    "year": {"type": "number"},
                },
                "required": ["farmId", "soilType", "irrigationType", "budgetBracket", "season", "year"],
            },
            _get_crop_candidates,
        ),
        plain_tool(
            "search_knowledge_base",
            "Search the verified farming knowledge base for diseases, agronomy, fertilizer, and schemes.",
            {
                "type": "object",
                "properties": {
                    "query": STR,
                    "cropType": OPT_STR,
                    "category": {"type": "string", "enum": ["disease", "agronomy", "fertilizer", "scheme", "general"]},
                },
                "required": ["query"],
            },
            _search_knowledge_base,
        ),
        account_tool(
            "search_past_conversations",
            "Search the farmer's past advisor conversation summaries.",
            {"type": "object", "properties": {"query": STR}, "required": ["query"]},
            _search_past_conversations,
        ),
    ]
    return {tool.name: tool for tool in tools}
