import numpy as np
import pandas as pd

from app.datasets.clean import (
    RAW_COLUMNS,
    clean_site,
    load_site_frame,
)


def _raw_frame(days: int = 40) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=days, freq="D")
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {
            "site": "test",
            "province": "Punjab",
            "latitude": 31.5,
            "longitude": 74.3,
            "date": index.strftime("%Y%m%d"),
            "t2m": rng.normal(20, 5, days),
            "t2m_max": rng.normal(26, 5, days),
            "t2m_min": rng.normal(14, 5, days),
            "t2m_range": rng.normal(12, 2, days),
            "t2mdew": rng.normal(8, 3, days),
            "prectotcorr": np.where(rng.random(days) < 0.2, rng.gamma(2, 5, days), 0.0),
            "rh2m": np.clip(rng.normal(55, 10, days), 0, 100),
            "ws2m": np.clip(rng.normal(2, 1, days), 0, None),
            "ws2m_max": np.clip(rng.normal(5, 2, days), 0, None),
            "wd2m": rng.uniform(0, 360, days),
            "ps": rng.normal(98, 1, days),
            "qv2m": np.clip(rng.normal(8, 2, days), 0, None),
            "allsky_sfc_sw_dwn": np.clip(rng.normal(18, 4, days), 0, None),
            "gwettop": np.clip(rng.normal(0.3, 0.1, days), 0, 1),
            "gwetroot": np.clip(rng.normal(0.35, 0.1, days), 0, 1),
            "gwetprof": np.clip(rng.normal(0.4, 0.1, days), 0, 1),
            "evland": np.clip(rng.normal(3, 1, days), 0, None),
            "evptrns": np.clip(rng.normal(5, 1, days), 0, None),
            "frost_days": np.zeros(days),
            "cdd0": np.clip(rng.normal(10, 3, days), 0, None),
        }
    )


def test_clean_site_outputs_expected_columns_and_types() -> None:
    cleaned, report = clean_site(_raw_frame().copy(), "test")
    for column in RAW_COLUMNS:
        assert column in cleaned.columns
    assert isinstance(cleaned.index, pd.DatetimeIndex)
    assert report.rows_out == len(cleaned)
    assert np.isfinite(cleaned["t2m_max"].to_numpy(dtype=float)).all()


def test_clean_site_swaps_inverted_temperature_bounds() -> None:
    frame = _raw_frame().copy()
    frame.loc[0, "t2m_max"] = 5.0
    frame.loc[0, "t2m_min"] = 30.0
    cleaned, _ = clean_site(frame, "test")
    assert cleaned["t2m_max"].iloc[0] >= cleaned["t2m_min"].iloc[0]


def test_clean_site_keeps_long_source_gaps_as_nan() -> None:
    frame = _raw_frame().copy()
    frame.loc[5:20, "allsky_sfc_sw_dwn"] = np.nan
    cleaned, report = clean_site(frame, "test")
    assert cleaned["allsky_sfc_sw_dwn"].isna().any()
    assert "allsky_sfc_sw_dwn" in report.column_missing


def test_clean_site_removes_duplicate_dates() -> None:
    frame = _raw_frame().copy()
    duplicated = pd.concat([frame, frame.iloc[[3]]], ignore_index=True)
    cleaned, report = clean_site(duplicated, "test")
    assert report.duplicate_days == 1
    assert not cleaned.index.duplicated().any()


def test_load_site_frame_parses_power_dates(tmp_path) -> None:
    frame = _raw_frame(10)
    path = tmp_path / "site.csv"
    frame.to_csv(path, index=False)
    loaded = load_site_frame(path)
    assert isinstance(loaded["date"].iloc[0], pd.Timestamp)
    assert loaded["date"].is_monotonic_increasing
