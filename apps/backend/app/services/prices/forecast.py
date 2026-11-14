"""Statistical price forecasting helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Any


def can_forecast(historical_prices: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_rows = sorted(historical_prices, key=lambda r: str(r.get("date", "")))
    row_count = len(sorted_rows)
    last_date = sorted_rows[-1].get("date") if row_count else None

    last_dt: datetime | None = None
    if last_date is not None:
        try:
            last_dt = datetime.fromisoformat(str(last_date))
        except Exception:
            last_dt = None

    stale_cutoff = datetime.utcnow() - timedelta(days=7)
    if row_count < 3:
        return {"ok": False, "reason": "insufficient_rows", "rowCount": row_count, "lastDate": last_date}
    if last_dt is None or last_dt < stale_cutoff:
        return {"ok": False, "reason": "stale_data", "rowCount": row_count, "lastDate": last_date}
    return {"ok": True, "reason": "ok", "rowCount": row_count, "lastDate": last_date}


def _holt_winters_forecast(values: list[float], horizon: int, alpha: float = 0.3, beta: float = 0.1):
    if len(values) < 2:
        base = values[0] if values else 0.0
        return {"forecasts": [base] * horizon, "trend": 0.0}

    level = values[0]
    trend = values[1] - values[0]
    for i in range(1, len(values)):
        value = values[i]
        prev_level = level
        level = alpha * value + (1 - alpha) * (prev_level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
    forecasts = [level + h * trend for h in range(1, horizon + 1)]
    return {"forecasts": forecasts, "trend": trend}


def _generate_reason(recommendation: str, predictions: list[dict[str, Any]], volatility_warning: bool) -> str:
    if not predictions:
        return "Not enough price data to recommend a selling moment."
    first = float(predictions[0]["predicted_price"])
    last = float(predictions[-1]["predicted_price"])
    direction = "rising" if last >= first else "falling"
    peak = max(predictions, key=lambda p: float(p["predicted_price"]))
    days_to_peak = predictions.index(peak) + 1

    if volatility_warning:
        if recommendation == "SELL":
            return (
                f"Prices look {direction}, but market data is limited or volatile. "
                "Sell only if cash is needed soon and monitor daily."
            )
        return (
            "Prices may rise, but confidence is low due to limited or volatile data. "
            "Hold if possible and check again soon."
        )
    if recommendation == "HOLD":
        suffix = "" if days_to_peak == 1 else "s"
        return (
            f"Prices are {direction} and may peak around {days_to_peak} day{suffix} from now. "
            "Holding could yield a better rate."
        )
    return f"Prices are expected to trend {direction} over the next two weeks. Selling sooner may be safer."


def forecast_prices(historical_prices: list[dict[str, Any]], horizon: int = 14) -> dict[str, Any]:
    sorted_rows = sorted(historical_prices, key=lambda r: str(r.get("date", "")))
    values = [float(r.get("modal_price") or 0) for r in sorted_rows]
    data_points = len(values)
    avg = mean(values) if values else 0.0
    volatility = pstdev(values) if data_points > 1 else 0.0
    cov = (volatility / avg) if avg > 0 else 0.0
    volatility_warning = data_points < 14 or cov > 0.15
    model_confidence = max(0.0, min(1.0, (data_points / 30) - cov))

    hw = _holt_winters_forecast(values, horizon)
    forecasts = hw["forecasts"]
    trend = hw["trend"]
    standard_error = volatility if data_points > 1 else avg * 0.05
    margin = 1.96 * standard_error

    try:
        last_dt = datetime.fromisoformat(str(sorted_rows[-1]["date"])) if sorted_rows else datetime.utcnow()
    except Exception:
        last_dt = datetime.utcnow()

    predictions = []
    for i in range(horizon):
        dt = last_dt + timedelta(days=i + 1)
        predicted = max(0.0, float(forecasts[i]))
        predictions.append(
            {
                "date": dt.date().isoformat(),
                "predicted_price": round(predicted * 100) / 100,
                "lower_bound": round(max(0.0, predicted - margin) * 100) / 100,
                "upper_bound": round((predicted + margin) * 100) / 100,
            }
        )

    recommendation = "HOLD" if trend > 0 else "SELL"
    return {
        "predictions": predictions,
        "recommendation": recommendation,
        "recommendation_reason": _generate_reason(recommendation, predictions, volatility_warning),
        "volatility_warning": volatility_warning,
        "model_confidence": round(model_confidence * 1000) / 1000,
    }
