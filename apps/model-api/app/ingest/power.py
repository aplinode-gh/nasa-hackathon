from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMETERS = [
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "RH2M",
    "WS2M",
    "ALLSKY_SFC_SW_DWN",
]
FILL_VALUE = -999.0


def fetch_power_daily(
    lat: float,
    lon: float,
    start: dt.date,
    end: dt.date,
    timeout: int = 90,
) -> pd.DataFrame:
    params = {
        "parameters": ",".join(POWER_PARAMETERS),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    response = requests.get(POWER_URL, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    parameter_data = payload["properties"]["parameter"]
    frame = pd.DataFrame({name: pd.Series(values) for name, values in parameter_data.items()})
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    frame = frame.sort_index()
    frame.columns = [column.lower() for column in frame.columns]
    return frame.replace(FILL_VALUE, float("nan")).astype("float64")


def fetch_power_daily_cached(
    lat: float,
    lon: float,
    start: dt.date,
    end: dt.date,
    cache_dir: Path,
) -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = f"power_{lat:.3f}_{lon:.3f}_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    path = cache_dir / filename
    if path.exists():
        return pd.read_csv(path, index_col=0, parse_dates=True)
    frame = fetch_power_daily(lat, lon, start, end)
    frame.to_csv(path)
    return frame


def load_local_power(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"date": str})
    frame["date"] = pd.to_datetime(frame["date"], format="%Y%m%d")
    frame = frame.set_index("date").sort_index()
    frame.columns = [column.lower() for column in frame.columns]
    return frame.replace(FILL_VALUE, float("nan"))
