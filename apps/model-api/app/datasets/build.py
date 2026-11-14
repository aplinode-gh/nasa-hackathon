from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd

from app.datasets.features import (
    apply_scenario,
    clean_dataset,
    clean_weather,
    synthetic_weather,
    weather_features,
)
from app.ingest.power import fetch_power_daily_cached
from app.knowledge import load_crops, load_soils
from app.simulation import simulate_crop_season

SITES = {
    "karachi": {"lat": 24.86, "lon": 67.01, "soil": "sandy_loam", "province": "Sindh"},
    "hyderabad": {"lat": 25.39, "lon": 68.37, "soil": "clay_loam", "province": "Sindh"},
    "sukkur": {"lat": 27.70, "lon": 68.86, "soil": "silty", "province": "Sindh"},
    "larkana": {"lat": 27.56, "lon": 68.21, "soil": "silty", "province": "Sindh"},
    "lahore": {"lat": 31.52, "lon": 74.36, "soil": "loamy", "province": "Punjab"},
    "faisalabad": {"lat": 31.42, "lon": 73.08, "soil": "loamy", "province": "Punjab"},
    "multan": {"lat": 30.19, "lon": 71.47, "soil": "loamy", "province": "Punjab"},
    "rawalpindi": {"lat": 33.60, "lon": 73.04, "soil": "sandy_loam", "province": "Punjab"},
    "gujranwala": {"lat": 32.19, "lon": 74.19, "soil": "loamy", "province": "Punjab"},
    "sialkot": {"lat": 32.49, "lon": 74.52, "soil": "clay_loam", "province": "Punjab"},
    "sargodha": {"lat": 32.08, "lon": 72.67, "soil": "loamy", "province": "Punjab"},
    "bahawalpur": {"lat": 29.40, "lon": 71.68, "soil": "sandy_loam", "province": "Punjab"},
    "sahiwal": {"lat": 30.67, "lon": 73.11, "soil": "clay_loam", "province": "Punjab"},
    "vehari": {"lat": 30.04, "lon": 72.35, "soil": "sandy", "province": "Punjab"},
    "dera_ghazi_khan": {"lat": 30.05, "lon": 70.64, "soil": "sandy_loam", "province": "Punjab"},
    "peshawar": {"lat": 34.01, "lon": 71.58, "soil": "clay_loam", "province": "Khyber Pakhtunkhwa"},
    "mardan": {"lat": 34.20, "lon": 72.04, "soil": "loamy", "province": "Khyber Pakhtunkhwa"},
    "swat": {"lat": 34.78, "lon": 72.36, "soil": "loamy", "province": "Khyber Pakhtunkhwa"},
    "quetta": {"lat": 30.18, "lon": 66.99, "soil": "sandy_loam", "province": "Balochistan"},
    "turbat": {"lat": 26.00, "lon": 63.05, "soil": "sandy", "province": "Balochistan"},
    "gwadar": {"lat": 25.13, "lon": 62.33, "soil": "sandy", "province": "Balochistan"},
    "islamabad": {"lat": 33.68, "lon": 73.05, "soil": "loamy", "province": "Islamabad"},
    "gilgit": {"lat": 35.92, "lon": 74.31, "soil": "rocky", "province": "Gilgit-Baltistan"},
    "muzaffarabad": {"lat": 34.37, "lon": 73.47, "soil": "loamy", "province": "Azad Kashmir"},
}

SEASON_START = {
    "winter": (11, 1),
    "summer": (6, 1),
    "spring": (3, 1),
    "autumn": (9, 1),
    "rainy": (7, 1),
    "windy": (2, 1),
}

SCENARIOS = [(0.0, 0.0), (2.0, -10.0), (2.0, 10.0), (4.0, -20.0)]
WATER_NEED_LEVEL = {"low": 0, "medium": 1, "high": 2}


def _season_start(year: int, season: str) -> dt.date:
    month, day = SEASON_START[season]
    return dt.date(year, month, day)


def _load_weather(
    site: dict, start: dt.date, end: dt.date, cache_dir: Path, offline: bool
) -> pd.DataFrame:
    if offline:
        return synthetic_weather(pd.date_range(start, end, freq="D"))
    return fetch_power_daily_cached(site["lat"], site["lon"], start, end, cache_dir)


def build_dataset(
    site_keys: list[str],
    start_year: int,
    end_year: int,
    cache_dir: Path,
    out_path: Path,
    offline: bool = False,
) -> pd.DataFrame:
    crops = load_crops()
    soils = load_soils()
    fetch_start = dt.date(start_year, 1, 1)
    fetch_end = dt.date(end_year + 1, 12, 31)
    rows: list[dict] = []

    for key in site_keys:
        site = SITES[key]
        soil = soils[site["soil"]]
        weather = _load_weather(site, fetch_start, fetch_end, cache_dir, offline)
        weather = clean_weather(weather)
        if weather.empty:
            continue

        for year in range(start_year, end_year + 1):
            for season in SEASON_START:
                start = _season_start(year, season)
                valid_crops = [
                    (crop_id, crop)
                    for crop_id, crop in crops.items()
                    if season in crop["season_windows"]
                ]
                for temp_delta, precip_delta in SCENARIOS:
                    adjusted = apply_scenario(weather, temp_delta, precip_delta)
                    for crop_id, crop in valid_crops:
                        duration = int(crop["duration_days"])
                        end = start + dt.timedelta(days=duration - 1)
                        window = adjusted.loc[pd.Timestamp(start):pd.Timestamp(end)]
                        if len(window) < int(duration * 0.9):
                            continue
                        result = simulate_crop_season(
                            crop,
                            soil,
                            window["t2m_max"].to_numpy(),
                            window["t2m_min"].to_numpy(),
                            window["prectotcorr"].to_numpy(),
                            site["lat"],
                            window.index.dayofyear.to_numpy(),
                        )
                        row = {
                            "site": key,
                            "province": site["province"],
                            "site_lat": site["lat"],
                            "site_lon": site["lon"],
                            "year": year,
                            "season": season,
                            "crop": crop_id,
                            "soil_type": site["soil"],
                            "soil_water_holding_capacity": soil["water_holding_capacity"],
                            "soil_drainage": soil["drainage"],
                            "soil_erosion_factor": soil["erosion_factor"],
                            "soil_salinity": soil["salinity"],
                            "crop_water_need_level": WATER_NEED_LEVEL[crop["water_need"]],
                            "crop_rooting_depth_m": crop["rooting_depth_m"],
                            "crop_duration_days": crop["duration_days"],
                            "crop_kc_mid": crop["kc_mid"],
                            "crop_n_fixing": int(crop["n_fixing"]),
                            "crop_erosion_cover": crop["erosion_cover"],
                            "crop_soc_effect": crop["soc_effect"],
                            "crop_market_score": crop["market_score"],
                            "crop_market_volatility": crop["market_volatility"],
                            "crop_pest_pressure": crop["pest_pressure"],
                            "scenario_temp_delta_c": temp_delta,
                            "scenario_precip_delta_pct": precip_delta,
                            **weather_features(window),
                            "label_irrigation_need_mm": result["irrigation_need_mm"],
                            "label_relative_yield_index": result["relative_yield_index"],
                            "label_water_stress_days": result["water_stress_days"],
                        }
                        rows.append(row)

    frame = clean_dataset(pd.DataFrame(rows))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix == ".parquet":
        frame.to_parquet(out_path, index=False)
    else:
        frame.to_csv(out_path, index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the rotation surrogate dataset")
    parser.add_argument("--sites", default="all", help="'all' or comma-separated site keys")
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2022)
    parser.add_argument("--out", default="artifacts/dataset.parquet")
    parser.add_argument("--cache-dir", default="data/cache")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    if args.sites.strip().lower() == "all":
        site_keys = list(SITES)
    else:
        site_keys = [key.strip() for key in args.sites.split(",") if key.strip()]

    unknown = [key for key in site_keys if key not in SITES]
    if unknown:
        raise SystemExit(f"Unknown sites: {', '.join(unknown)}. Choose from {', '.join(SITES)}")

    frame = build_dataset(
        site_keys=site_keys,
        start_year=args.start_year,
        end_year=args.end_year,
        cache_dir=Path(args.cache_dir),
        out_path=Path(args.out),
        offline=args.offline,
    )
    print(f"Wrote {len(frame)} rows to {args.out}")
    if not frame.empty:
        print(frame.groupby("province").size().to_string())
        print(
            frame[["site", "crop", "label_irrigation_need_mm", "label_relative_yield_index"]].head()
        )


if __name__ == "__main__":
    main()
