from __future__ import annotations

import numpy as np
import pandas as pd

WEATHER_COLUMNS = [
    "t2m_max",
    "t2m_min",
    "prectotcorr",
    "rh2m",
    "ws2m",
    "allsky_sfc_sw_dwn",
]


def clean_weather(frame: pd.DataFrame) -> pd.DataFrame:
    clean = frame.copy()
    for column in WEATHER_COLUMNS:
        if column in clean.columns:
            clean[column] = pd.to_numeric(clean[column], errors="coerce")
    present = [column for column in WEATHER_COLUMNS if column in clean.columns]
    if not present:
        return clean
    clean = clean.dropna(subset=present)
    if "prectotcorr" in clean.columns:
        clean["prectotcorr"] = clean["prectotcorr"].clip(lower=0.0)
    if "rh2m" in clean.columns:
        clean["rh2m"] = clean["rh2m"].clip(0.0, 100.0)
    if "ws2m" in clean.columns:
        clean["ws2m"] = clean["ws2m"].clip(lower=0.0)
    if "allsky_sfc_sw_dwn" in clean.columns:
        clean["allsky_sfc_sw_dwn"] = clean["allsky_sfc_sw_dwn"].clip(lower=0.0)
    clean = clean.sort_index()
    clean = clean[~clean.index.duplicated(keep="first")]
    return clean


def apply_scenario(
    weather: pd.DataFrame, temp_delta_c: float, precip_delta_pct: float
) -> pd.DataFrame:
    adjusted = weather.copy()
    adjusted["t2m_max"] = adjusted["t2m_max"] + temp_delta_c
    adjusted["t2m_min"] = adjusted["t2m_min"] + temp_delta_c
    factor = 1.0 + precip_delta_pct / 100.0
    adjusted["prectotcorr"] = (adjusted["prectotcorr"] * factor).clip(lower=0.0)
    return adjusted


def _max_dry_spell(precip: np.ndarray, threshold: float = 1.0) -> float:
    best = 0
    current = 0
    for value in precip:
        if value < threshold:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return float(best)


def weather_features(weather: pd.DataFrame) -> dict[str, float]:
    tmax = weather["t2m_max"].to_numpy(dtype=float)
    tmin = weather["t2m_min"].to_numpy(dtype=float)
    precip = weather["prectotcorr"].to_numpy(dtype=float)
    rh = weather["rh2m"].to_numpy(dtype=float)
    wind = weather["ws2m"].to_numpy(dtype=float)
    solar = weather["allsky_sfc_sw_dwn"].to_numpy(dtype=float)

    rain_mean = float(precip.mean())
    rain_cv = float(precip.std() / rain_mean) if rain_mean > 0 else 0.0
    tmean = (tmax + tmin) / 2.0
    gdd = float(np.maximum(tmean - 5.0, 0.0).sum())

    return {
        "rain_total_mm": round(float(precip.sum()), 2),
        "rain_cv": round(rain_cv, 4),
        "heavy_rain_days": float((precip >= 25.0).sum()),
        "tmax_mean_c": round(float(tmax.mean()), 3),
        "tmin_min_c": round(float(tmin.min()), 3),
        "frost_days": float((tmin < 0.0).sum()),
        "gdd": round(gdd, 2),
        "rh_mean": round(float(rh.mean()), 3),
        "wind_mean": round(float(wind.mean()), 3),
        "solar_mean": round(float(solar.mean()), 3),
        "dry_spell_max_days": _max_dry_spell(precip),
    }


def clean_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    clean = frame.replace([np.inf, -np.inf], np.nan)
    clean = clean.dropna(subset=["label_irrigation_need_mm", "label_relative_yield_index"])
    clean = clean[clean["label_irrigation_need_mm"] >= 0.0]
    clean = clean[
        (clean["label_relative_yield_index"] >= 0.0)
        & (clean["label_relative_yield_index"] <= 1.0)
    ]
    subset = [
        "site",
        "year",
        "season",
        "crop",
        "scenario_temp_delta_c",
        "scenario_precip_delta_pct",
    ]
    clean = clean.drop_duplicates(subset=subset)
    return clean.reset_index(drop=True)


def synthetic_weather(index: pd.DatetimeIndex, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    count = len(index)
    day_of_year = index.dayofyear.to_numpy()
    seasonal = 18.0 + 12.0 * np.sin(2.0 * np.pi * (day_of_year - 100) / 365.0)
    tmax = seasonal + 8.0 + rng.normal(0.0, 2.0, count)
    tmin = seasonal - 8.0 + rng.normal(0.0, 2.0, count)
    precip = np.where(rng.random(count) < 0.15, rng.gamma(1.5, 8.0, count), 0.0)
    return pd.DataFrame(
        {
            "t2m_max": tmax,
            "t2m_min": tmin,
            "prectotcorr": precip,
            "rh2m": np.clip(rng.normal(55.0, 15.0, count), 5.0, 100.0),
            "ws2m": np.clip(rng.normal(2.5, 1.0, count), 0.0, None),
            "allsky_sfc_sw_dwn": np.clip(rng.normal(18.0, 5.0, count), 0.0, None),
        },
        index=index,
    )
