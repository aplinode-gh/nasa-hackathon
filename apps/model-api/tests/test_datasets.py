import numpy as np
import pandas as pd

from app.datasets.features import (
    apply_scenario,
    clean_dataset,
    clean_weather,
    synthetic_weather,
    weather_features,
)


def test_clean_weather_drops_fill_and_clips() -> None:
    index = pd.date_range("2022-01-01", periods=3, freq="D")
    frame = pd.DataFrame(
        {
            "t2m_max": [30.0, -999.0, 32.0],
            "t2m_min": [12.0, 13.0, 14.0],
            "prectotcorr": [-1.0, 2.0, 5.0],
            "rh2m": [40.0, 50.0, 120.0],
            "ws2m": [-2.0, 1.0, 2.0],
            "allsky_sfc_sw_dwn": [10.0, 12.0, -3.0],
        },
        index=index,
    )
    cleaned = clean_weather(frame)
    assert len(cleaned) == 2
    assert (cleaned["prectotcorr"] >= 0).all()
    assert (cleaned["rh2m"] <= 100).all()
    assert (cleaned["ws2m"] >= 0).all()
    assert (cleaned["allsky_sfc_sw_dwn"] >= 0).all()


def test_weather_features_keys() -> None:
    index = pd.date_range("2022-01-01", periods=30, freq="D")
    frame = synthetic_weather(index)
    features = weather_features(frame)
    assert features["rain_total_mm"] >= 0.0
    assert features["dry_spell_max_days"] >= 0.0
    assert "gdd" in features


def test_apply_scenario_shifts_temperature_and_rain() -> None:
    index = pd.date_range("2022-01-01", periods=10, freq="D")
    frame = synthetic_weather(index)
    adjusted = apply_scenario(frame, 2.0, -50.0)
    assert np.allclose(adjusted["t2m_max"], frame["t2m_max"] + 2.0)
    assert np.allclose(adjusted["prectotcorr"], frame["prectotcorr"] * 0.5)


def test_clean_dataset_drops_invalid_labels() -> None:
    frame = pd.DataFrame(
        {
            "site": ["a", "a", "a"],
            "year": [2020, 2020, 2020],
            "season": ["winter"] * 3,
            "crop": ["wheat"] * 3,
            "scenario_temp_delta_c": [0.0] * 3,
            "scenario_precip_delta_pct": [0.0] * 3,
            "label_irrigation_need_mm": [10.0, -5.0, 20.0],
            "label_relative_yield_index": [0.9, 1.2, 0.8],
        }
    )
    cleaned = clean_dataset(frame)
    assert len(cleaned) == 1
