from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

POWER_PARAMETERS = [
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "T2M_RANGE",
    "T2MDEW",
    "PRECTOTCORR",
    "RH2M",
    "WS2M",
    "WS2M_MAX",
    "WD2M",
    "PS",
    "QV2M",
    "ALLSKY_SFC_SW_DWN",
    "GWETTOP",
    "GWETROOT",
    "GWETPROF",
    "EVLAND",
    "EVPTRNS",
    "FROST_DAYS",
    "CDD0",
]

FILL_VALUE = -999.0


def _parse_parameter_dates(payload: dict) -> pd.DataFrame:
    parameter_data = payload["properties"]["parameter"]
    frame = pd.DataFrame({name: pd.Series(values) for name, values in parameter_data.items()})
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    frame = frame.sort_index()
    frame.columns = [column.lower() for column in frame.columns]
    return frame.replace(FILL_VALUE, float("nan")).astype("float64")


def fetch_power_daily(
    lat: float,
    lon: float,
    start: dt.date,
    end: dt.date,
    timeout: int = 240,
    parameters: list[str] | None = None,
    retries: int = 5,
) -> pd.DataFrame:
    params = {
        "parameters": ",".join(parameters or POWER_PARAMETERS),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(POWER_URL, params=params, timeout=timeout)
            response.raise_for_status()
            return _parse_parameter_dates(response.json())
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                dt_now = attempt * 3
                import time

                time.sleep(dt_now)

    raise RuntimeError(f"POWER request failed for ({lat}, {lon}): {last_error}")


def fetch_power_daily_cached(
    lat: float,
    lon: float,
    start: dt.date,
    end: dt.date,
    cache_dir: Path,
    parameters: list[str] | None = None,
) -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = f"power_{lat:.3f}_{lon:.3f}_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    path = cache_dir / filename
    if path.exists():
        return pd.read_csv(path, index_col=0, parse_dates=True)
    frame = fetch_power_daily(lat, lon, start, end, parameters=parameters)
    frame.to_csv(path)
    return frame


def load_local_power(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"date": str})
    frame["date"] = pd.to_datetime(frame["date"], format="%Y%m%d")
    frame = frame.set_index("date").sort_index()
    frame.columns = [column.lower() for column in frame.columns]
    return frame.replace(FILL_VALUE, float("nan"))


def write_site_file(
    site_key: str,
    province: str,
    lat: float,
    lon: float,
    frame: pd.DataFrame,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{site_key}.csv"

    export = frame.copy()
    export.insert(0, "site", site_key)
    export.insert(1, "province", province)
    export.insert(2, "latitude", lat)
    export.insert(3, "longitude", lon)
    export.insert(4, "date", export.index.strftime("%Y%m%d"))
    export = export.reset_index(drop=True)
    export.to_csv(path, index=False, encoding="utf-8")
    return path
