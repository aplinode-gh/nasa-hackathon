import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.predict import (
    CLEAN_DIR,
    MODEL_DIR,
    TARGET_BOUNDS,
    _fmt,
    detect_signals,
)

client = TestClient(app)

ARTIFACTS_READY = (
    (CLEAN_DIR / "training_table.parquet").exists()
    and (MODEL_DIR / "metrics.json").exists()
)

requires_artifacts = pytest.mark.skipif(
    not ARTIFACTS_READY, reason="Run prepare_dataset.py and train_forecast.py first"
)


def test_detect_signals_matches_aliases() -> None:
    assert "frost" in detect_signals("Will there be a frost next month?")
    assert "rainfall" in detect_signals("How much barish should we expect?")
    assert "soil_moisture" in detect_signals("Is the soil dry?")


def test_detect_signals_falls_back_to_core_signals() -> None:
    assert detect_signals("hello") == ["temperature", "rainfall", "soil_moisture"]


def test_format_never_renders_negative_zero() -> None:
    assert _fmt(-0.001, 1) == "0.0"
    assert _fmt(12.345, 1) == "12.3"
    assert _fmt(None) == "n/a"


@requires_artifacts
def test_sites_endpoint_lists_pakistan_sites() -> None:
    response = client.get("/sites")
    assert response.status_code == 200
    sites = response.json()["sites"]
    assert len(sites) >= 20
    keys = {site["site"] for site in sites}
    assert {"lahore", "karachi", "quetta"}.issubset(keys)


@requires_artifacts
def test_forecast_endpoint_returns_bands() -> None:
    response = client.get("/forecast/lahore?season=rabi")
    assert response.status_code == 200
    body = response.json()
    assert body["observed_year"] >= 2020
    assert body["target_year"] == body["observed_year"] + 1

    for target, entry in body["predictions"].items():
        if entry["p50"] is None:
            continue
        assert entry["p10"] <= entry["p50"] <= entry["p90"], target
        low, high = TARGET_BOUNDS.get(target, (None, None))
        if low is not None:
            assert entry["p10"] >= low - 1e-6, target
        if high is not None:
            assert entry["p90"] <= high + 1e-6, target


@requires_artifacts
def test_ask_endpoint_answers_rainfall_question() -> None:
    response = client.post(
        "/ask",
        json={"site": "multan", "season": "kharif", "question": "Will rainfall change?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["findings"]
    assert "rainfall" in body["signals_detected"]
    assert body["caveats"]


@requires_artifacts
def test_forecast_unknown_site_returns_404() -> None:
    response = client.get("/forecast/atlantis")
    assert response.status_code == 404


def test_forecast_rejects_unknown_season() -> None:
    response = client.get("/forecast/lahore?season=monsoon")
    assert response.status_code == 422


@requires_artifacts
def test_predictions_are_finite() -> None:
    response = client.get("/forecast/islamabad?season=annual")
    body = response.json()
    for target, entry in body["predictions"].items():
        if entry["p50"] is None:
            continue
        assert np.isfinite(entry["p50"]), target
