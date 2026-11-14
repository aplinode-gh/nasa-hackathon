from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _payload() -> dict:
    return {
        "field": {
            "lat": 30.19,
            "lon": 71.47,
            "soil_type": "loamy",
            "current_crop": "wheat",
            "target_season": "winter",
            "irrigation_type": "canal",
        },
        "priorities": {"water": 0.4, "income": 0.2, "soil_health": 0.25, "risk": 0.15},
        "scenario": {"temp_delta_c": 2.0, "precip_delta_pct": -10},
    }


def test_compare_returns_baseline_and_alternatives() -> None:
    response = client.post("/compare-rotations", json=_payload())
    assert response.status_code == 200

    strategies = response.json()["strategies"]
    assert len(strategies) >= 3
    assert strategies[0]["is_baseline"] is True
    assert any(not strategy["is_baseline"] for strategy in strategies[1:])

    for strategy in strategies:
        assert 0.0 <= strategy["score"] <= 1.0
        band = strategy["outcomes"]["water_use_mm"]
        assert band["p10"] <= band["p50"] <= band["p90"]


def test_unknown_crop_is_rejected() -> None:
    payload = _payload()
    payload["field"]["current_crop"] = "dragonfruit"

    response = client.post("/compare-rotations", json=payload)
    assert response.status_code == 422
