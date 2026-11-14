from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.datasets.clean import RAW_COLUMNS, clean_site, load_site_frame
from app.datasets.signals import (
    INDICATOR_COLUMNS,
    SEASON_FEATURE_COLUMNS,
    add_forecast_targets,
    add_indicators,
    long_term_trends,
    seasonal_features,
)
from app.ingest.modis import attach_ndvi, fetch_ndvi

NUMERIC_FEATURES = SEASON_FEATURE_COLUMNS + INDICATOR_COLUMNS

TREND_COLUMNS = [
    "tmean_c_per_decade",
    "heat_days_35_per_decade",
    "precip_mm_per_decade",
    "soil_moisture_per_decade",
    "frost_days_per_decade",
]


def _save_arrays(frame: pd.DataFrame, out_dir: Path) -> dict[str, list[int]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    shapes: dict[str, list[int]] = {}

    features = [column for column in NUMERIC_FEATURES if column in frame.columns]
    matrix = frame[features].to_numpy(dtype=np.float32)
    np.save(out_dir / "X_features.npy", matrix)
    shapes["X_features.npy"] = list(matrix.shape)

    meta_columns = ["site", "province", "season", "year"]
    meta = frame[[c for c in meta_columns if c in frame.columns]].to_numpy(dtype=object)
    np.save(out_dir / "meta.npy", meta)
    shapes["meta.npy"] = list(meta.shape)

    targets = sorted(column for column in frame.columns if column.startswith("target_next_"))
    if targets:
        target_matrix = frame[targets].to_numpy(dtype=np.float32)
        np.save(out_dir / "y_targets.npy", target_matrix)
        shapes["y_targets.npy"] = list(target_matrix.shape)
        (out_dir / "target_names.json").write_text(
            json.dumps(targets, indent=2), encoding="utf-8"
        )

    (out_dir / "feature_names.json").write_text(
        json.dumps(features, indent=2), encoding="utf-8"
    )

    return shapes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean Pakistan NASA POWER data and build model-ready arrays"
    )
    parser.add_argument("--datasets-dir", default="datasets")
    parser.add_argument("--out-dir", default="artifacts/clean")
    parser.add_argument("--sites", default="all")
    parser.add_argument(
        "--ndvi",
        action="store_true",
        help=(
            "Ingest MODIS MOD13Q1 NDVI from ORNL. Very slow (minutes per site-year) "
            "because of server-side limits; cached under data/cache/ndvi."
        ),
    )
    parser.add_argument("--ndvi-start-year", type=int, default=2000)
    parser.add_argument("--ndvi-end-year", type=int, default=2024)
    args = parser.parse_args()

    datasets_dir = Path(args.datasets_dir)
    out_dir = Path(args.out_dir)
    manifest_path = datasets_dir / "power_manifest.csv"
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest: {manifest_path}. Run harvest first.")

    manifest = pd.read_csv(manifest_path)
    if args.sites.strip().lower() != "all":
        keep = [key.strip() for key in args.sites.split(",") if key.strip()]
        manifest = manifest[manifest["site"].isin(keep)]

    cleaned_dir = out_dir / "cleaned"
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    clean_reports = []
    seasonal_parts = []

    for _, row in manifest.iterrows():
        site = str(row["site"])
        path = datasets_dir / str(row["file"])
        if not path.exists():
            print(f"{site}: missing {path}, skipping")
            continue

        raw = load_site_frame(path)
        cleaned, report = clean_site(raw, site)
        clean_reports.append(report.as_dict())

        ndvi_summary = ""
        if args.ndvi:
            ndvi = fetch_ndvi(
                site,
                float(row["latitude"]),
                float(row["longitude"]),
                args.ndvi_start_year,
                args.ndvi_end_year,
                Path("data/cache/ndvi"),
            )
            cleaned, info = attach_ndvi(cleaned, ndvi)
            if info["ndvi_points"]:
                ndvi_summary = f", ndvi points={info['ndvi_points']}"
            else:
                ndvi_summary = ", ndvi unavailable"

        parquet_path = cleaned_dir / f"{site}.parquet"
        cleaned.reset_index().to_parquet(parquet_path, index=False)

        seasonal = seasonal_features(cleaned, site)
        if seasonal.empty:
            print(f"{site}: no seasonal rows produced")
            continue
        seasonal_parts.append(seasonal)
        print(
            f"{site}: {len(raw)} raw -> {len(cleaned)} clean days -> "
            f"{len(seasonal)} season-years{ndvi_summary}"
        )

    if not seasonal_parts:
        raise SystemExit("No seasonal features produced.")

    seasonal_all = pd.concat(seasonal_parts, ignore_index=True)
    seasonal_all = add_indicators(seasonal_all)
    trends = long_term_trends(seasonal_all)

    trend_index = trends.set_index(["site", "season"]) if not trends.empty else None
    if trend_index is not None:
        for column in TREND_COLUMNS:
            if column in trend_index.columns:
                keys = list(zip(seasonal_all["site"], seasonal_all["season"]))
                seasonal_all[column] = [
                    trend_index[column].get(key, np.nan) for key in keys
                ]

    labelled = add_forecast_targets(seasonal_all)

    seasonal_all.to_parquet(out_dir / "seasonal_features.parquet", index=False)
    labelled.to_parquet(out_dir / "training_table.parquet", index=False)
    trends.to_csv(out_dir / "long_term_trends.csv", index=False)
    pd.DataFrame(clean_reports).to_csv(out_dir / "clean_report.csv", index=False)

    shapes = _save_arrays(labelled, out_dir)

    summary = {
        "sites": int(seasonal_all["site"].nunique()),
        "season_rows": int(len(seasonal_all)),
        "training_rows": int(len(labelled)),
        "features": len(
            [column for column in NUMERIC_FEATURES if column in labelled.columns]
        ),
        "targets": len(
            [column for column in labelled.columns if column.startswith("target_next_")]
        ),
        "years": [int(seasonal_all["year"].min()), int(seasonal_all["year"].max())],
        "arrays": shapes,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
