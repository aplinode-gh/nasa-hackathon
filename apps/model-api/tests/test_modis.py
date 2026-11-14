import numpy as np
import pandas as pd

from app.ingest.modis import attach_ndvi, fetch_ndvi


def _daily(days: int = 40) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=days, freq="D")
    return pd.DataFrame({"t2m_max": np.linspace(20, 30, days)}, index=index)


def test_attach_ndvi_interpolates_onto_daily_index() -> None:
    daily = _daily()
    ndvi = pd.Series(
        [0.2, 0.4, 0.6],
        index=pd.to_datetime(["2020-01-01", "2020-01-17", "2020-02-02"]),
    )
    frame, info = attach_ndvi(daily, ndvi)
    assert "ndvi" in frame.columns
    assert info["ndvi_points"] == 3
    # Daily index is 2020-01-01..2020-02-09; composites stop on 2020-02-02,
    # so the last 7 days are intentionally left empty.
    assert 0.8 < info["ndvi_coverage"] < 0.9
    assert frame["ndvi"].iloc[0] == 0.2
    assert np.isnan(frame["ndvi"].iloc[-1])


def test_attach_ndvi_does_not_extrapolate_past_last_composite() -> None:
    daily = _daily()
    ndvi = pd.Series(
        [0.3, 0.5],
        index=pd.to_datetime(["2020-01-01", "2020-01-10"]),
    )
    frame, _ = attach_ndvi(daily, ndvi)
    assert np.isnan(frame["ndvi"].iloc[-1])
    assert not np.isnan(frame["ndvi"].iloc[5])


def test_attach_ndvi_with_empty_series_keeps_frame() -> None:
    daily = _daily()
    frame, info = attach_ndvi(daily, pd.Series(dtype=float))
    assert info["ndvi_points"] == 0
    assert "ndvi" not in frame.columns


def test_fetch_ndvi_uses_cache(tmp_path) -> None:
    cache = tmp_path / "ndvi"
    cache.mkdir()
    cached = pd.DataFrame({"date": ["2020-01-01", "2020-01-17"], "ndvi": [0.3, 0.5]})
    cached.to_csv(cache / "ndvi_lahore.csv", index=False)
    series = fetch_ndvi("lahore", 31.5, 74.3, 2020, 2020, cache)
    assert len(series) == 2
    assert float(series.iloc[0]) == 0.3
