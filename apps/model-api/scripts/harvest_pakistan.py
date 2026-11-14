from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.datasets.build import SITES
from app.ingest.power import POWER_PARAMETERS, fetch_power_daily, write_site_file

DEFAULT_START = dt.date(1981, 1, 1)
DEFAULT_END = dt.date(2024, 12, 31)


def _describe(frame: pd.DataFrame) -> dict:
    return {
        "rows": int(len(frame)),
        "columns": int(frame.shape[1]),
        "start": frame.index.min().strftime("%Y-%m-%d"),
        "end": frame.index.max().strftime("%Y-%m-%d"),
        "missing_fraction": round(float(frame.isna().to_numpy().mean()), 6),
    }


def harvest(
    site_keys: list[str],
    start: dt.date,
    end: dt.date,
    out_dir: Path,
    force: bool,
    parameters: list[str],
) -> pd.DataFrame:
    rows: list[dict] = []

    for index, key in enumerate(site_keys, start=1):
        site = SITES[key]
        path = out_dir / f"{key}.csv"
        label = f"[{index}/{len(site_keys)}] {key}"

        if path.exists() and not force:
            existing = pd.read_csv(path, dtype={"date": str})
            existing["date"] = pd.to_datetime(existing["date"], format="%Y%m%d")
            existing = existing.set_index("date").sort_index()
            has_all = all(column in existing.columns for column in parameters)
            if has_all and len(existing) > 1000:
                print(f"{label}: cached ({len(existing)} rows)")
                rows.append(
                    {
                        "site": key,
                        "province": site["province"],
                        "latitude": site["lat"],
                        "longitude": site["lon"],
                        "rows": int(len(existing)),
                        "start": existing.index.min().strftime("%Y%m%d"),
                        "end": existing.index.max().strftime("%Y%m%d"),
                        "columns": int(existing.shape[1]),
                        "file": f"power/{key}.csv",
                    }
                )
                continue

        print(f"{label}: fetching {start} -> {end} ...", flush=True)
        frame = fetch_power_daily(
            site["lat"], site["lon"], start, end, parameters=parameters
        )
        write_site_file(key, site["province"], site["lat"], site["lon"], frame, out_dir)
        info = _describe(frame)
        print(
            f"{label}: saved {info['rows']} rows, {info['columns']} cols, "
            f"missing={info['missing_fraction']:.4f}"
        )
        rows.append(
            {
                "site": key,
                "province": site["province"],
                "latitude": site["lat"],
                "longitude": site["lon"],
                "rows": info["rows"],
                "start": frame.index.min().strftime("%Y%m%d"),
                "end": frame.index.max().strftime("%Y%m%d"),
                "columns": info["columns"],
                "file": f"power/{key}.csv",
            }
        )

    manifest = pd.DataFrame(rows)
    manifest_path = out_dir.parent / "power_manifest.csv"
    manifest.to_csv(manifest_path, index=False, encoding="utf-8")
    print(f"\nManifest written: {manifest_path} ({len(manifest)} sites)")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest NASA POWER data for Pakistan sites")
    parser.add_argument("--sites", default="all", help="'all' or comma-separated site keys")
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--end", default=DEFAULT_END.isoformat())
    parser.add_argument("--out", default="datasets/power")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.sites.strip().lower() == "all":
        site_keys = list(SITES)
    else:
        site_keys = [key.strip() for key in args.sites.split(",") if key.strip()]

    unknown = [key for key in site_keys if key not in SITES]
    if unknown:
        raise SystemExit(f"Unknown sites: {', '.join(unknown)}")

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    parameters = [name.lower() for name in POWER_PARAMETERS]

    manifest = harvest(site_keys, start, end, Path(args.out), args.force, parameters)
    total_cells = int(manifest["rows"].sum() * (len(parameters) + 5))
    summary = {
        "sites": int(len(manifest)),
        "parameters": parameters,
        "total_rows": int(manifest["rows"].sum()),
        "total_cells": total_cells,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "provinces": sorted(manifest["province"].unique().tolist()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
