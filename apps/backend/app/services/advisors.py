"""Advisor agent definitions and triage wiring."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.serialization import parse_json_field
from app.db.session import query, query_one
from app.services.ai.agent import AgentDef
from app.services.ai.context import (
    build_crop_advisor_instructions,
    build_crop_recommendation_instructions,
    build_farm_data_instructions,
    build_handoff_instructions,
    build_prices_instructions,
    build_schemes_instructions,
    build_triage_instructions,
    build_weather_instructions,
    get_current_season,
)
from app.services.advisor_tools import build_advisor_tools

AGENT_KEYS = {
    "Crop Advisor": "crop_advisor",
    "Crop Recommendation Advisor": "crop_recommendation",
    "Weather Advisor": "weather",
    "Farm Data Advisor": "farm_data",
    "Prices Advisor": "prices",
    "Schemes Advisor": "schemes",
    "Agronomist Handoff": "handoff",
    "Triage": "triage",
}


async def build_farmer_context(
    account_id: str,
    conversation_id: str,
    history_text: str,
) -> dict[str, Any]:
    user = await query_one("SELECT full_name FROM users WHERE id = $1", account_id)
    farms = await query(
        """
        SELECT id, name, location, district, lat, lng, acres, crops, growth_stages, primary_crop
        FROM farms
        WHERE account_id = $1 AND archived_at IS NULL
        ORDER BY created_at DESC
        """,
        account_id,
    )
    summaries = await query(
        """
        SELECT title, summary, updated_at FROM advisor_conversations
        WHERE account_id = $1 AND summary IS NOT NULL AND id <> $2
        ORDER BY updated_at DESC LIMIT 3
        """,
        account_id,
        conversation_id,
    )

    farm_list = []
    for farm in farms or []:
        crops = parse_json_field(farm.get("crops"), [])
        stage = "unknown"
        stages = parse_json_field(farm.get("growth_stages"), {})
        if isinstance(stages, dict) and stages:
            primary = farm.get("primary_crop")
            stage = str(stages.get(primary) or next(iter(stages.values())))
        farm_list.append(
            {
                "name": farm.get("name"),
                "location": farm.get("location"),
                "district": farm.get("district"),
                "lat": farm.get("lat"),
                "lng": farm.get("lng"),
                "acres": farm.get("acres"),
                "crops": ", ".join(str(item) for item in crops) if isinstance(crops, list) else str(crops or ""),
                "stage": stage,
            }
        )

    season = get_current_season()
    now = datetime.now()
    summary_lines = [
        f'- "{row.get("title")}" ({str(row.get("updated_at"))[:10]}): {row.get("summary")}'
        for row in summaries or []
    ]
    return {
        "accountId": account_id,
        "farmerName": (user or {}).get("full_name") or "Farmer",
        "language": "en",
        "farms": farm_list,
        "currentSeason": season["season"],
        "seasonPhase": season["phase"],
        "currentDate": now.strftime("%B %d, %Y"),
        "currentMonth": now.month,
        "district": (farm_list[0]["district"] if farm_list else "Unknown"),
        "conversationHistory": history_text,
        "recentSummaries": "\n".join(summary_lines),
    }


def build_advisor_agents(context: dict[str, Any]) -> dict[str, AgentDef]:
    tools = build_advisor_tools(context["accountId"])

    crop_advisor = AgentDef(
        name="Crop Advisor",
        instructions=build_crop_advisor_instructions(),
        tools=[tools["search_knowledge_base"]],
        handoff_description=(
            "Handles crop diseases, pests, agronomy, fertilizer, seed treatment, irrigation scheduling, "
            "vegetables, fruits, pulses, and basic livestock health."
        ),
    )
    crop_recommendation = AgentDef(
        name="Crop Recommendation Advisor",
        instructions=build_crop_recommendation_instructions(),
        tools=[
            tools["get_my_farms"],
            tools["get_farm_details"],
            tools["check_soil_crop_fit"],
            tools["get_weather"],
            tools["get_weather_forecast"],
            tools["get_market_prices"],
            tools["get_crop_candidates"],
            tools["search_knowledge_base"],
        ],
        handoff_description=(
            "Handles what to plant, crop selection, seasonal planting advice, and crop rotation planning "
            "based on farm data, weather, and market prices."
        ),
    )
    weather = AgentDef(
        name="Weather Advisor",
        instructions=build_weather_instructions(),
        tools=[tools["get_weather"], tools["get_weather_forecast"]],
        handoff_description=(
            "Handles weather forecasts, rain, temperature, humidity, and spray windows for any district in Pakistan."
        ),
    )
    farm_data = AgentDef(
        name="Farm Data Advisor",
        instructions=build_farm_data_instructions(),
        tools=[
            tools["get_my_farms"],
            tools["get_my_records"],
            tools["get_farm_details"],
            tools["check_soil_crop_fit"],
            tools["get_my_weather_records"],
            tools["get_my_farm_weather"],
            tools["get_my_seasons"],
            tools["get_season_expenses"],
            tools["get_profit_loss_summary"],
            tools["get_my_crop_recommendations"],
            tools["get_farm_plan"],
            tools["search_knowledge_base"],
        ],
        handoff_description=(
            "Handles the farmer's own farms, records, planting history, costs, live weather at their farms, "
            "profit/loss, and saved crop plans."
        ),
    )
    prices = AgentDef(
        name="Prices Advisor",
        instructions=build_prices_instructions(),
        tools=[tools["get_market_prices"]],
        handoff_description="Handles mandi prices, market rates, crop selling advice, and price trends.",
    )
    schemes = AgentDef(
        name="Schemes Advisor",
        instructions=build_schemes_instructions(),
        tools=[tools["search_knowledge_base"]],
        handoff_description=(
            "Handles government schemes, subsidies, Kissan Card, loans, crop insurance, and support programs."
        ),
    )
    handoff = AgentDef(
        name="Agronomist Handoff",
        instructions=build_handoff_instructions(),
        handoff_description=(
            "Handles cases where the AI cannot confidently answer: complex disease identification, unknown symptoms, "
            "safety-critical dosages, or explicit requests for a human expert."
        ),
    )
    triage = AgentDef(
        name="Triage",
        instructions=build_triage_instructions(context),
        tools=[tools["search_knowledge_base"], tools["search_past_conversations"]],
        handoffs=[
            "Crop Advisor",
            "Crop Recommendation Advisor",
            "Weather Advisor",
            "Farm Data Advisor",
            "Prices Advisor",
            "Schemes Advisor",
            "Agronomist Handoff",
        ],
    )

    return {
        crop_advisor.name: crop_advisor,
        crop_recommendation.name: crop_recommendation,
        weather.name: weather,
        farm_data.name: farm_data,
        prices.name: prices,
        schemes.name: schemes,
        handoff.name: handoff,
        triage.name: triage,
    }
