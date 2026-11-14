from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

MODIS_URL = "https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset"
MODIS_BAND = "250m_16_days_NDVI"
MODIS_SCALE = 0.0001
MODIS_FILL = -3000


def _modis_date(year: int, day_of_year: int = 1) -> str:
    return f"A{year}{day_of_year:03d}"


def _chunk_windows(start_year: int, end_year: int, span: int = 1) -> list[tuple[int, int]]:
    windows = []
    year = start_year
    while year <= end_year:
        windows.append((year, min(year + span - 1, end_year)))
        year += span
    return windows


def _sub_windows(start_year: int, end_year: int) -> list[tuple[str, str]]:
    """Split a year range into <=8 composite-tile windows.

    The ORNL subset endpoint rejects >10 tiles and its reverse proxy drops
    responses that take longer than about a minute, so chunks stay small.
    """
    windows: list[tuple[str, str]] = []
    for year in range(start_year, end_year + 1):
        day = 1
        while day <= 361:
            end = min(day + 127, 361)
            windows.append((_modis_date(year, day), _modis_date(year, end)))
            day = end + 16
    return windows


def _request_chunk(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    retries: int = 3,
    timeout: int = 90,
) -> list[dict]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "startDate": start_date,
        "endDate": end_date,
        "band": MODIS_BAND,
        "kmAboveBelow": 0,
        "kmLeftRight": 0,
    }

    last_error: str | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(MODIS_URL, params=params, timeout=timeout)
            if response.status_code == 200:
                payload = response.json()
                return payload.get("subset", []) or []
            last_error = f"HTTP {response.status_code}"
            if response.status_code == 400:
                break
        except Exception as exc:  # network flake, timeouts, proxy errors
            last_error = str(exc)[:120]
        time.sleep(2 * attempt)

    print(f"    NDVI chunk {start_date}-{end_date} failed: {last_error}")
    return []


def fetch_ndvi(
    site: str,
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    cache_dir: Path,
    force: bool = False,
) -> pd.Series:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"ndvi_{site}.csv"
    if path.exists() and not force:
        cached = pd.read_csv(path, parse_dates=["date"])
        if not cached.empty:
            return cached.set_index("date")["ndvi"].astype(float)

    records: list[dict] = []
    windows = _sub_windows(start_year, end_year)
    for position, (start_date, end_date) in enumerate(windows, start=1):
        subset = _request_chunk(lat, lon, start_date, end_date)
        for entry in subset:
            raw = entry.get("data") or []
            if not raw:
                continue
            value = float(raw[0])
            if value == MODIS_FILL:
                continue
            ndvi = value * MODIS_SCALE
            if not 0.0 <= ndvi <= 1.0:
                continue
            records.append({"date": entry["calendar_date"], "ndvi": ndvi})
        if position % 8 == 0:
            print(f"    NDVI {site}: {position}/{len(windows)} windows")
        time.sleep(1.0)

    if not records:
        return pd.Series(dtype=float, name="ndvi")

    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = (
        frame.drop_duplicates(subset="date")
        .sort_values("date")
        .reset_index(drop=True)
    )
    frame.to_csv(path, index=False, encoding="utf-8")
    return frame.set_index("date")["ndvi"].astype(float)


def attach_ndvi(
    daily: pd.DataFrame,
    ndvi: pd.Series,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Resample 16-day NDVI composites onto the daily weather index."""
    if ndvi.empty:
        return daily, {"ndvi_coverage": 0.0, "ndvi_points": 0}

    series = ndvi.copy()
    target_index = daily.index
    combined_index = series.index.union(target_index)
    resampled = (
        series.reindex(combined_index)
        .interpolate(method="time")
        .reindex(target_index)
    )
    # Do not extrapolate NDVI beyond the first/last composite.
    resampled = resampled.where(
        (target_index >= series.index.min()) & (target_index <= series.index.max())
    )

    frame = daily.copy()
    frame["ndvi"] = resampled.to_numpy()
    coverage = float(np.isfinite(frame["ndvi"]).mean())
    return frame, {
        "ndvi_coverage": round(coverage, 4),
        "ndvi_points": int(len(series)),
    }
