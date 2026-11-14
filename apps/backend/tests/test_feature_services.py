"""Unit and smoke tests for the restored feature modules."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.detect import diagnose_image  # noqa: E402
from app.services.pest import build_forecast, stage_merge  # noqa: E402
from app.services.profit_loss import (  # noqa: E402
    compute_break_even,
    compute_pl,
    default_projected_costs,
    get_crop_unit,
    get_season_start_date,
)


class ProfitLossCalculationTests(unittest.TestCase):
    def test_compute_pl_profit(self) -> None:
        result = compute_pl(50000, 40000, 0, 60000)
        self.assertEqual(result["status"], "profit")
        self.assertEqual(result["netProfitLoss"], 20000)
        self.assertEqual(result["roi"], 50.0)
        self.assertEqual(result["variance"]["absolute"], -10000)

    def test_compute_pl_loss_and_zero(self) -> None:
        self.assertEqual(compute_pl(10000, 15000, 0, 10000)["status"], "loss")
        self.assertEqual(compute_pl(10000, 10000, 0, 10000)["status"], "break_even")
        self.assertIsNone(compute_pl(0, 0, 0, 0)["roi"])

    def test_break_even(self) -> None:
        result = compute_break_even(100000, 2500, 40, 2)
        self.assertIsNotNone(result)
        self.assertEqual(result["yield"], "40.0 units")
        self.assertEqual(result["price"], "PKR 1250.0 per unit")
        self.assertIsNone(compute_break_even(100000, None, 40, 2))

    def test_crop_unit_and_season_start(self) -> None:
        self.assertEqual(get_crop_unit("mango"), "Dozen")
        self.assertEqual(get_crop_unit("unknown"), "Maund")
        self.assertEqual(get_season_start_date("Summer").month, 5)

    def test_default_projected_costs_scale_with_acres(self) -> None:
        costs = default_projected_costs(2)
        self.assertEqual(len(costs), 5)
        seed = next(item for item in costs if item["category"] == "seed")
        self.assertEqual(seed["total_projected_pkr"], seed["per_acre_cost_pkr"] * 2)


class PestForecastTests(unittest.TestCase):
    farm = {
        "id": "farm-1",
        "name": "Test farm",
        "growth_stages": {"wheat": "Flowering"},
    }

    def test_demo_forecast_shape(self) -> None:
        forecast = build_forecast(self.farm, "wheat", None)
        self.assertTrue(forecast["weather_data_unavailable"])
        self.assertEqual(len(forecast["days"]), 7)
        for day in forecast["days"]:
            self.assertGreaterEqual(day["risk_score"], 0)
            self.assertLessEqual(day["risk_score"], 100)
            self.assertIn(day["status"], ("active", "monitoring"))

    def test_weather_forecast_uses_days(self) -> None:
        weather = {
            "days": [
                {
                    "date": "2026-01-01",
                    "temp_max": 24,
                    "temp_min": 12,
                    "precip_mm": 0,
                    "humidity": 80,
                }
            ]
        }
        forecast = build_forecast(self.farm, "wheat", weather)
        self.assertFalse(forecast["weather_data_unavailable"])
        self.assertEqual(forecast["days"][0]["date"], "2026-01-01")

    def test_stage_merge(self) -> None:
        self.assertEqual(stage_merge({"wheat": "Sowing"}, "wheat", "Flowering"), {"wheat": "Flowering"})
        self.assertEqual(stage_merge(None, "rice", "Vegetative"), {"rice": "Vegetative"})


class DetectFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnose_image_contract(self) -> None:
        data = b"not-a-real-jpeg-but-deterministic"
        first = await diagnose_image(data, "wheat_leaf.jpg")
        second = await diagnose_image(data, "wheat_leaf.jpg")
        self.assertEqual(first, second)
        for key in (
            "diseaseName",
            "confidence",
            "severity",
            "crop",
            "causes",
            "steps",
            "rescanTiming",
            "caution",
        ):
            self.assertIn(key, first)
        self.assertGreaterEqual(first["confidence"], 0)
        self.assertLessEqual(first["confidence"], 1)
        self.assertIsInstance(first["steps"], list)


class RouteRegistrationTests(unittest.TestCase):
    def test_feature_routes_are_registered(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        paths = app.openapi()["paths"]
        for path in (
            "/api/profit-loss",
            "/api/profit-loss/{season_id}",
            "/api/profit-loss/{season_id}/expenses",
            "/api/detect",
            "/api/detect/history",
            "/api/detect/chats",
            "/api/detect/chat",
            "/api/pest/forecast",
            "/api/pest/alerts",
        ):
            self.assertIn(path, paths)

        client = TestClient(app)
        self.assertEqual(client.get("/api/profit-loss").status_code, 401)
        self.assertEqual(client.get("/api/detect/history").status_code, 401)
        self.assertEqual(client.get("/api/pest/alerts").status_code, 401)


if __name__ == "__main__":
    unittest.main()
