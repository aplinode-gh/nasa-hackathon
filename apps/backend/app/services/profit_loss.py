"""Profit / Loss calculation helpers (ported from the Next.js app)."""

from __future__ import annotations

from datetime import date
from typing import Any

DEFAULT_PROJECTED_COSTS: list[tuple[str, float]] = [
    ("seed", 6000.0),
    ("fertilizer", 12000.0),
    ("labor", 10000.0),
    ("irrigation", 5000.0),
    ("transport", 3000.0),
]

CROP_UNITS: dict[str, str] = {
    "sugarcane": "Mann",
    "rice": "Mann",
    "mango": "Dozen",
    "banana": "Dozen",
    "apple": "Dozen",
    "olive": "Kg",
    "date palm": "Kg",
}


def get_season_start_date(season: str, today: date | None = None) -> date:
    """Return the conventional start date for a season in the current year."""
    ref = today or date.today()
    month_day = {
        "Summer": (5, 1),
        "Winter": (11, 1),
        "Rainy": (7, 1),
        "Dry": (1, 1),
    }.get(season, (1, 1))
    return date(ref.year, month_day[0], month_day[1])


def compute_variance(actual_total: float, projected_total: float) -> dict[str, Any]:
    absolute = actual_total - projected_total
    percentage = round((absolute / projected_total) * 1000) / 10 if projected_total > 0 else None
    return {"absolute": round(absolute, 2), "percentage": percentage}


def compute_roi(actual_revenue: float, total_actual_cost: float) -> float | None:
    if total_actual_cost == 0:
        return None
    return round(((actual_revenue - total_actual_cost) / total_actual_cost) * 1000) / 10


def compute_break_even(
    total_investment: float,
    expected_price_per_unit: float | None,
    expected_yield_per_acre: float | None,
    acres: float,
) -> dict[str, str] | None:
    if (
        not expected_price_per_unit
        or not expected_yield_per_acre
        or expected_price_per_unit <= 0
        or expected_yield_per_acre <= 0
        or acres <= 0
    ):
        return None
    total_expected_yield = expected_yield_per_acre * acres
    break_even_yield = total_investment / expected_price_per_unit
    break_even_price = total_investment / total_expected_yield
    return {
        "yield": f"{round(break_even_yield * 100) / 100} units",
        "price": f"PKR {round(break_even_price * 100) / 100} per unit",
    }


def compute_pl(
    total_projected_cost: float,
    total_actual_cost: float,
    projected_revenue: float,
    actual_revenue: float,
) -> dict[str, Any]:
    net = actual_revenue - total_actual_cost
    if net > 0:
        status = "profit"
    elif net < 0:
        status = "loss"
    else:
        status = "break_even"
    return {
        "netProfitLoss": round(net, 2),
        "roi": compute_roi(actual_revenue, total_actual_cost),
        "variance": compute_variance(total_actual_cost, total_projected_cost),
        "status": status,
    }


def get_crop_unit(crop_id: str) -> str:
    return CROP_UNITS.get((crop_id or "").lower(), "Maund")


def default_projected_costs(acres: float) -> list[dict[str, Any]]:
    return [
        {
            "category": category,
            "per_acre_cost_pkr": per_acre,
            "total_projected_pkr": round(per_acre * acres, 2),
        }
        for category, per_acre in DEFAULT_PROJECTED_COSTS
    ]
