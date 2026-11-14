import numpy as np
import pandas as pd

from app.datasets.signals import (
    EXPECTED_SEASON_DAYS,
    MIN_SEASON_COVERAGE,
    add_forecast_targets,
    add_indicators,
    long_term_trends,
    seasonal_features,
)


def _daily_frame(years: int = 5, seed: int = 3) -> pd.DataFrame:
    index = pd.date_range("2015-01-01", periods=365 * years, freq="D")
    rng = np.random.default_rng(seed)
    doy = np.arange(len(index)) % 365
    seasonal = 22.0 + 10.0 * np.sin(2 * np.pi * (doy - 100) / 365.0)
    tmax = seasonal + 7.0
    tmin = seasonal - 8.0
    precip = np.where(rng.random(len(index)) < 0.12, rng.gamma(2.0, 6.0, len(index)), 0.0)
    return pd.DataFrame(
        {
            "site": "test",
            "province": "Punjab",
            "latitude": 31.5,
            "longitude": 74.3,
            "t2m": (tmax + tmin) / 2.0,
            "t2m_max": tmax,
            "t2m_min": tmin,
            "t2m_range": tmax - tmin,
            "t2mdew": tmin,
            "prectotcorr": precip,
            "rh2m": np.full(len(index), 55.0),
            "ws2m": np.full(len(index), 2.0),
            "ws2m_max": np.full(len(index), 5.0),
            "wd2m": np.full(len(index), 180.0),
            "ps": np.full(len(index), 98.0),
            "qv2m": np.full(len(index), 8.0),
            "allsky_sfc_sw_dwn": np.full(len(index), 18.0),
            "gwettop": np.clip(0.3 + precip / 100.0, 0, 1),
            "gwetroot": np.clip(0.35 + precip / 100.0, 0, 1),
            "gwetprof": np.clip(0.4 + precip / 100.0, 0, 1),
            "evland": np.clip(seasonal / 10.0, 0, None),
            "evptrns": np.clip(seasonal / 6.0, 0, None),
            "frost_days": (tmin < 0).astype(float),
            "cdd0": np.clip(seasonal - 18.0, 0, None),
        },
        index=index,
    )


def test_seasonal_features_cover_all_seasons() -> None:
    seasonal = seasonal_features(_daily_frame(), "test")
    assert not seasonal.empty
    assert set(seasonal["season"].unique()) == {"rabi", "kharif", "annual"}
    assert seasonal["site"].eq("test").all()


def test_seasonal_features_require_full_coverage() -> None:
    frame = _daily_frame(years=2)
    seasonal = seasonal_features(frame, "test")
    expected_min = min(EXPECTED_SEASON_DAYS.values()) * MIN_SEASON_COVERAGE
    assert (seasonal["days_observed"] >= expected_min).all()


def test_indicators_are_finite_and_in_range() -> None:
    seasonal = add_indicators(seasonal_features(_daily_frame(years=6), "test"))
    for column in ("temp_shift_z", "heat_stress_index", "vegetation_stress_index"):
        values = seasonal[column].to_numpy(dtype=float)
        assert np.isfinite(values).all(), column
    assert (seasonal["rainfall_reliability"] <= 1.0).all()


def test_forecast_targets_exclude_last_season() -> None:
    seasonal = add_indicators(seasonal_features(_daily_frame(years=6), "test"))
    labelled = add_forecast_targets(seasonal)
    assert "target_next_tmean_c" in labelled.columns
    assert labelled["target_next_tmean_c"].notna().any()
    for season, group in labelled.groupby("season"):
        assert group["year"].max() < seasonal[seasonal["season"] == season]["year"].max()


def test_long_term_trends_one_row_per_site_season() -> None:
    seasonal = add_indicators(seasonal_features(_daily_frame(years=8), "test"))
    trends = long_term_trends(seasonal)
    assert len(trends) == 3
    assert trends["tmean_c_per_decade"].notna().all()
