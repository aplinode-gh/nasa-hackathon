"""Tool implementations for the app-control agent."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from app.core.serialization import parse_json_field
from app.db.session import execute, query, query_one
from app.services.ai.agent import Tool
from app.services.farms.weather import fetch_current_weather

NAVIGATION_ALLOWLIST = [
    "/dashboard",
    "/farms",
    "/records",
    "/prices",
    "/profit-loss",
    "/detect",
    "/schemes",
    "/weather",
    "/advisor",
]

PAGE_LABELS = {
    "/dashboard": "Dashboard",
    "/farms": "Farms",
    "/records": "Records",
    "/prices": "Prices",
    "/profit-loss": "Profit & Loss",
    "/detect": "Crop Doctor",
    "/schemes": "Schemes",
    "/weather": "Weather",
    "/advisor": "Advisor",
}

RECORD_TYPES = ["sowing", "planting", "irrigation", "fertilizer", "pesticide", "disease", "harvest"]


def _crops(value: Any) -> str:
    parsed = parse_json_field(value, value)
    if isinstance(parsed, list):
        return ", ".join(str(item) for item in parsed)
    return str(parsed or "")


def _stages(value: Any) -> str:
    parsed = parse_json_field(value, {})
    if isinstance(parsed, dict) and parsed:
        return ", ".join(f"{crop}: {stage}" for crop, stage in parsed.items())
    return "not set"


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def _season_label() -> str:
    month = datetime.now().month
    if month in (5, 6, 7, 8, 9):
        return "Summer" if month in (5, 6) else "Rainy"
    if month in (10, 11):
        return "Winter"
    return "Dry"


def _year_label(event_date: str) -> str:
    try:
        year = date.fromisoformat(event_date).year
    except ValueError:
        year = date.today().year
    return f"{year}-{str(year + 1)[-2:]}"


def _record_line(row: dict[str, Any]) -> str:
    line = f"• [{row.get('farm_name')}] {row.get('title') or row.get('type')} ({row.get('type')}) — {row.get('event_date')}"
    if row.get("note"):
        line += f": {row['note']}"
    if row.get("yield_qty") is not None:
        line += f" | Yield: {row['yield_qty']}"
    costs = []
    if row.get("labor_cost") is not None:
        costs.append(f"labor Rs {row['labor_cost']}")
    if row.get("transport_cost") is not None:
        costs.append(f"transport Rs {row['transport_cost']}")
    if costs:
        line += f" | Costs: {', '.join(costs)}"
    return line


async def _navigate(args: dict[str, Any]) -> str:
    path = str(args.get("path") or "")
    normalized = path if path.startswith("/") else f"/{path}"
    if normalized not in NAVIGATION_ALLOWLIST:
        return f'I can\'t navigate to "{normalized}". I can only take you to: {", ".join(NAVIGATION_ALLOWLIST)}.'
    return json.dumps(
        {
            "type": "navigation_button",
            "path": normalized,
            "label": f"Go to {PAGE_LABELS.get(normalized, normalized)}",
        }
    )


def _handoff(args: dict[str, Any]) -> str:
    return json.dumps({"type": "navigation_button", "path": "/advisor", "label": "Open Advisor Chat"})


async def _dashboard_summary(account_id: str, args: dict[str, Any]) -> str:
    farms = await query_one(
        "SELECT count(*) AS count FROM farms WHERE account_id = $1 AND archived_at IS NULL", account_id
    )
    total = await query_one("SELECT count(*) AS count FROM records WHERE account_id = $1", account_id)
    recent = await query_one(
        "SELECT count(*) AS count FROM records WHERE account_id = $1 AND event_date >= current_date - 7", account_id
    )
    alerts = await query_one(
        "SELECT count(*) AS count FROM weather_alerts WHERE account_id = $1 AND read_at IS NULL AND dismissed_at IS NULL",
        account_id,
    )
    farm_count = int((farms or {}).get("count") or 0)
    total_count = int((total or {}).get("count") or 0)
    recent_count = int((recent or {}).get("count") or 0)
    alert_count = int((alerts or {}).get("count") or 0)
    return (
        f"Dashboard summary:\n• Farms registered: {farm_count}\n• Total activities logged: {total_count}\n"
        f"• Activities logged this week: {recent_count}\n• Unread alerts: {alert_count}\n\n"
        + ("You have unread alerts — check the notifications bell." if alert_count else "No new alerts.")
        + ("" if recent_count else "\nNo recent activity — consider logging irrigation, spraying, or harvesting.")
    )


async def _farm_summary(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    sql = (
        "SELECT id, name, location, district, acres, crops, growth_stages FROM farms "
        "WHERE account_id = $1 AND archived_at IS NULL"
    )
    params: list[Any] = [account_id]
    if farm_id:
        sql += " AND id = $2"
        params.append(farm_id)
    rows = await query(sql + " ORDER BY created_at DESC", *params)
    if not rows:
        return "You have no farms registered yet. You can add one from the Farms section."
    lines = [
        f"• {row['name']} ({row.get('location')}, {row.get('district')}): {row.get('acres')} acres, "
        f"crops: {_crops(row.get('crops'))}, stages: {_stages(row.get('growth_stages'))}"
        for row in rows
    ]
    return f"You have {len(rows)} farm{'s' if len(rows) != 1 else ''}:\n" + "\n".join(lines)


async def _farm_details(account_id: str, args: dict[str, Any]) -> str:
    farm = await query_one(
        """
        SELECT id, name, location, district, acres, crops, growth_stages, soil_type,
               irrigation_method, primary_crop, sowing_date
        FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL
        """,
        args.get("farmId"),
        account_id,
    )
    if not farm:
        return "Farm not found. Please check your farm list."
    return (
        f"Farm: {farm['name']}\nLocation: {farm.get('location')}, {farm.get('district')}\n"
        f"Size: {farm.get('acres')} acres\nSoil type: {farm.get('soil_type') or 'not recorded'}\n"
        f"Irrigation: {farm.get('irrigation_method') or 'not recorded'}\n"
        f"Primary crop: {farm.get('primary_crop') or 'not set'}\n"
        f"Sowing date: {farm.get('sowing_date') or 'not recorded'}\n"
        f"Crops: {_crops(farm.get('crops'))}\nGrowth stages: {_stages(farm.get('growth_stages'))}"
    )


async def _recent_records(account_id: str, args: dict[str, Any]) -> str:
    days = int(args.get("days") or 14)
    farm_id = args.get("farmId")
    record_type = args.get("recordType")
    conditions = ["r.account_id = $1", "r.event_date >= current_date - $2::int"]
    params: list[Any] = [account_id, days]
    idx = 3
    if farm_id:
        conditions.append(f"r.farm_id = ${idx}")
        params.append(farm_id)
        idx += 1
    if record_type:
        conditions.append(f"r.type = ${idx}")
        params.append(record_type)
        idx += 1
    rows = await query(
        f"""
        SELECT r.id, f.name AS farm_name, r.type, r.event_date, r.title, r.note,
               r.yield_qty, r.labor_cost, r.transport_cost
        FROM records r JOIN farms f ON f.id = r.farm_id
        WHERE {' AND '.join(conditions)}
        ORDER BY r.event_date DESC, r.created_at DESC LIMIT 20
        """,
        *params,
    )
    if not rows:
        return f"No records found in the last {days} days."
    return f"Recent activities (last {days} days):\n" + "\n".join(_record_line(row) for row in rows)


async def _record_details(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    record_type = args.get("recordType")
    limit = int(args.get("limit") or 20)
    conditions = ["r.account_id = $1"]
    params: list[Any] = [account_id]
    idx = 2
    if farm_id:
        conditions.append(f"r.farm_id = ${idx}")
        params.append(farm_id)
        idx += 1
    if record_type:
        conditions.append(f"r.type = ${idx}")
        params.append(record_type)
        idx += 1
    rows = await query(
        f"""
        SELECT r.id, r.farm_id, f.name AS farm_name, r.type, r.event_date, r.title, r.note,
               r.yield_qty, r.labor_cost, r.transport_cost
        FROM records r JOIN farms f ON f.id = r.farm_id
        WHERE {' AND '.join(conditions)}
        ORDER BY r.event_date DESC, r.created_at DESC LIMIT ${idx}
        """,
        *params,
        limit,
    )
    if not rows:
        return "No matching records found."
    return "Recent farm records:\n" + "\n".join(_record_line(row) for row in rows)


async def _price_summary(args: dict[str, Any]) -> str:
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
        ORDER BY p.crop_id, p.mandi_id, p.date DESC LIMIT 20
        """,
        args.get("crop"),
        args.get("market"),
    )
    if not rows:
        return "No current mandi price data found."
    lines = [
        f"• {row['crop_name']} at {row['mandi_name']}: Rs {float(row['modal_price']):,.0f}/maund "
        f"(Rs {float(row['min_price']):,.0f}–{float(row['max_price']):,.0f}, {row['date']})"
        for row in rows
    ]
    return "Current mandi prices:\n" + "\n".join(lines)


async def _profit_loss_summary(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    season = args.get("season")
    limit = int(args.get("limit") or 10)
    conditions = ["s.account_id = $1", "s.archived_at IS NULL"]
    params: list[Any] = [account_id]
    idx = 2
    if farm_id:
        conditions.append(f"s.farm_id = ${idx}")
        params.append(farm_id)
        idx += 1
    if season:
        conditions.append(f"s.season ILIKE ${idx}")
        params.append(f"%{season}%")
        idx += 1
    rows = await query(
        f"""
        SELECT s.id, c.name_en AS crop_name, f.name AS farm_name, s.season, s.year, s.acres, s.status,
               COALESCE(SUM(e.amount), 0) AS total_actual_cost,
               COALESCE(SUM(pc.total_projected_pkr), 0) AS total_projected_cost,
               COALESCE(s.actual_price, 0) AS actual_price
        FROM seasons s
        JOIN farms f ON f.id = s.farm_id
        JOIN crops c ON c.id = s.crop_id
        LEFT JOIN expenses e ON e.season_id = s.id
        LEFT JOIN projected_costs pc ON pc.season_id = s.id
        WHERE {' AND '.join(conditions)}
        GROUP BY s.id, c.name_en, f.name, s.season, s.year, s.acres, s.status, s.actual_price
        ORDER BY s.created_at DESC LIMIT ${idx}
        """,
        *params,
        limit,
    )
    if not rows:
        return "No seasons found. Start tracking a season from the Profit/Loss page."
    lines = []
    for row in rows:
        revenue = float(row.get("actual_price") or 0)
        cost = float(row.get("total_actual_cost") or 0)
        net = revenue - cost
        roi = ((revenue - cost) / cost * 100) if cost > 0 else 0
        label = f"Profit: PKR {net:,.0f}" if net >= 0 else f"Loss: PKR {abs(net):,.0f}"
        lines.append(
            f"• [{row['farm_name']}] {row['crop_name']} ({row['season']} {row['year']}): "
            f"{label}, ROI: {roi:.1f}% ({row['acres']} acres)"
        )
    return "Profit/Loss summary:\n" + "\n".join(lines)


async def _weather_summary(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    if not farm_id:
        return "Please specify a farm ID to get weather for that location."
    farm = await query_one(
        "SELECT lat, lng, name, location FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL",
        farm_id,
        account_id,
    )
    if not farm:
        return "Farm not found. Please check your farm list."
    weather = await fetch_current_weather(float(farm["lat"]), float(farm["lng"]))
    if weather.get("temp_c") is None and not weather.get("condition"):
        return f"Weather data temporarily unavailable for {farm['name']}."
    parts = [f"Weather for {farm['name']} ({farm.get('location')}):"]
    if weather.get("temp_c") is not None:
        parts.append(f"• Temperature: {weather['temp_c']}°C")
    if weather.get("condition"):
        parts.append(f"• Condition: {weather['condition']}")
    if weather.get("humidity") is not None:
        parts.append(f"• Humidity: {weather['humidity']}%")
    if weather.get("wind_kph") is not None:
        parts.append(f"• Wind: {weather['wind_kph']} km/h")
    return "\n".join(parts)


async def _create_record(account_id: str, args: dict[str, Any]) -> str:
    farm_id = args.get("farmId")
    event_date = args.get("eventDate")
    confirmed = bool(args.get("confirmed"))
    if not confirmed:
        message = (
            f"Create a new {args.get('type')} record:\n• Farm: {farm_id}\n• Date: {event_date}\n"
            f"• Title: {args.get('title')}\n• Note: {args.get('note')}\n\n"
            "Do you want to create this record? Reply yes or no."
        )
        return json.dumps({"type": "confirmation", "action": "create_record", "message": message, "data": args})

    farm = await query_one(
        "SELECT id FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL", farm_id, account_id
    )
    if not farm:
        return "Farm not found or does not belong to you."

    record_type = args.get("type")
    if record_type not in RECORD_TYPES:
        return "Invalid record type."
    try:
        event_date_value = date.fromisoformat(str(event_date))
    except ValueError:
        return "Invalid date. Use YYYY-MM-DD."

    row = await query_one(
        """
        INSERT INTO records (account_id, farm_id, type, season, year, event_date, title, note,
                             yield_qty, labor_cost, transport_cost)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        RETURNING id
        """,
        account_id,
        farm_id,
        record_type,
        _season_label(),
        _year_label(str(event_date)),
        event_date_value,
        args.get("title"),
        args.get("note"),
        _number(args.get("yieldQty")),
        _number(args.get("laborCost")),
        _number(args.get("transportCost")),
    )
    return f"Record created successfully (ID: {(row or {}).get('id', 'unknown')}). You can view it in the Records section."


async def _update_record(account_id: str, args: dict[str, Any]) -> str:
    record_id = args.get("recordId")
    existing = await query_one(
        """
        SELECT id, farm_id, type, event_date, title, note, yield_qty, labor_cost, transport_cost
        FROM records WHERE id = $1 AND account_id = $2
        """,
        record_id,
        account_id,
    )
    if not existing:
        return "Record not found or does not belong to you."

    if not args.get("confirmed"):
        changes = []
        for key, label in (
            ("farmId", "farm"),
            ("type", "type"),
            ("eventDate", "date"),
            ("title", "title"),
            ("note", "note"),
            ("yieldQty", "yield"),
            ("laborCost", "labor cost"),
            ("transportCost", "transport cost"),
        ):
            if args.get(key) not in (None, ""):
                changes.append(f"• {label}: {args.get(key)}")
        if not changes:
            return "No changes detected. Please specify what you want to update."
        message = f"Update record {record_id}:\n" + "\n".join(changes) + "\n\nDo you want to apply these changes? Reply yes or no."
        return json.dumps({"type": "confirmation", "action": "update_record", "message": message, "data": args})

    sets = []
    values: list[Any] = [record_id, account_id]
    idx = 3
    mapping = {
        "farmId": "farm_id",
        "type": "type",
        "title": "title",
        "note": "note",
        "yieldQty": "yield_qty",
        "laborCost": "labor_cost",
        "transportCost": "transport_cost",
    }
    for key, column in mapping.items():
        if args.get(key) not in (None, ""):
            value = _number(args[key]) if key in ("yieldQty", "laborCost", "transportCost") else args[key]
            sets.append(f"{column} = ${idx}")
            values.append(value)
            idx += 1
    if args.get("eventDate"):
        try:
            sets.append(f"event_date = ${idx}")
            values.append(date.fromisoformat(str(args["eventDate"])))
            idx += 1
        except ValueError:
            return "Invalid date. Use YYYY-MM-DD."
    if not sets:
        return "No fields to update."

    await execute(f"UPDATE records SET {', '.join(sets)} WHERE id = $1 AND account_id = $2", *values)
    return f"Record {record_id} updated successfully."


async def _delete_record(account_id: str, args: dict[str, Any]) -> str:
    record_id = args.get("recordId")
    existing = await query_one(
        "SELECT id, type, event_date FROM records WHERE id = $1 AND account_id = $2", record_id, account_id
    )
    if not existing:
        return "Record not found or does not belong to you."
    if not args.get("confirmed"):
        message = (
            f"Delete this record permanently?\n• Type: {existing['type']}\n• Date: {existing['event_date']}\n"
            f"• ID: {record_id}\n\nThis cannot be undone. Reply yes or no."
        )
        return json.dumps({"type": "confirmation", "action": "delete_record", "message": message, "data": {"recordId": record_id}})

    await execute("DELETE FROM records WHERE id = $1 AND account_id = $2", record_id, account_id)
    return f"Record {record_id} has been deleted."


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def build_app_control_tools(account_id: str) -> dict[str, Tool]:
    def bound(name: str, description: str, parameters: dict[str, Any], handler) -> Tool:
        async def wrapped(args: dict[str, Any]) -> str:
            return await handler(account_id, args)

        return Tool(name=name, description=description, parameters=parameters, handler=wrapped)

    def plain(name: str, description: str, parameters: dict[str, Any], handler) -> Tool:
        return Tool(name=name, description=description, parameters=parameters, handler=handler)

    tools = [
        plain(
            "navigate_to_page",
            "Navigate the farmer to a specific app page. Path must be in the allowlist.",
            _schema({"path": {"type": "string"}}, ["path"]),
            _navigate,
        ),
        plain(
            "handoff_to_advisor",
            "Transfer the farmer to the Agropioo Advisor for detailed crop or disease advice.",
            _schema({}),
            _handoff,
        ),
        bound(
            "get_dashboard_summary",
            "Get farm count, activity counts, recent activity, and unread alerts.",
            _schema({}),
            _dashboard_summary,
        ),
        bound(
            "get_farm_summary",
            "Get a summary of the farmer's farms with crops and growth stages.",
            _schema({"farmId": {"type": "string"}}),
            _farm_summary,
        ),
        bound(
            "get_farm_details",
            "Get detailed information about a specific farm including soil, irrigation, crops, and stages.",
            _schema({"farmId": {"type": "string"}}, ["farmId"]),
            _farm_details,
        ),
        bound(
            "get_recent_records",
            "Get recent farm activity records across farms.",
            _schema(
                {
                    "days": {"type": "number"},
                    "farmId": {"type": "string"},
                    "recordType": {"type": "string", "enum": RECORD_TYPES},
                }
            ),
            _recent_records,
        ),
        bound(
            "get_record_details",
            "Get details of farm activity records, optionally filtered by farm or type.",
            _schema(
                {
                    "farmId": {"type": "string"},
                    "recordType": {"type": "string", "enum": RECORD_TYPES},
                    "limit": {"type": "number"},
                }
            ),
            _record_details,
        ),
        plain(
            "get_price_summary",
            "Get current mandi prices for crops.",
            _schema({"crop": {"type": "string"}, "market": {"type": "string"}}),
            _price_summary,
        ),
        bound(
            "get_profit_loss_summary",
            "Get a profit/loss summary for the farmer's seasons with costs, revenue, net, and ROI.",
            _schema(
                {
                    "farmId": {"type": "string"},
                    "season": {"type": "string"},
                    "limit": {"type": "number"},
                }
            ),
            _profit_loss_summary,
        ),
        bound(
            "get_weather_summary",
            "Get current weather conditions for a specific farm.",
            _schema({"farmId": {"type": "string"}}),
            _weather_summary,
        ),
        bound(
            "create_record",
            "Create a farm activity record after explicit confirmation.",
            _schema(
                {
                    "farmId": {"type": "string"},
                    "type": {"type": "string", "enum": RECORD_TYPES},
                    "eventDate": {"type": "string"},
                    "title": {"type": "string"},
                    "note": {"type": "string"},
                    "yieldQty": {"type": "string"},
                    "laborCost": {"type": "string"},
                    "transportCost": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                ["farmId", "type", "eventDate", "title", "note"],
            ),
            _create_record,
        ),
        bound(
            "update_record",
            "Update a farm activity record after explicit confirmation.",
            _schema(
                {
                    "recordId": {"type": "string"},
                    "farmId": {"type": "string"},
                    "type": {"type": "string", "enum": RECORD_TYPES},
                    "eventDate": {"type": "string"},
                    "title": {"type": "string"},
                    "note": {"type": "string"},
                    "yieldQty": {"type": "string"},
                    "laborCost": {"type": "string"},
                    "transportCost": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                ["recordId"],
            ),
            _update_record,
        ),
        bound(
            "delete_record",
            "Delete a farm activity record after explicit confirmation.",
            _schema({"recordId": {"type": "string"}, "confirmed": {"type": "boolean"}}, ["recordId"]),
            _delete_record,
        ),
    ]
    return {tool.name: tool for tool in tools}
