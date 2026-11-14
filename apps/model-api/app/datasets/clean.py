from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

RAW_COLUMNS = [
    "t2m",
    "t2m_max",
    "t2m_min",
    "t2m_range",
    "t2mdew",
    "prectotcorr",
    "rh2m",
    "ws2m",
    "ws2m_max",
    "wd2m",
    "ps",
    "qv2m",
    "allsky_sfc_sw_dwn",
    "gwettop",
    "gwetroot",
    "gwetprof",
    "evland",
    "evptrns",
    "frost_days",
    "cdd0",
]

UNIT_BOUNDS = {
    "t2m": (-30.0, 55.0),
    "t2m_max": (-30.0, 60.0),
    "t2m_min": (-40.0, 50.0),
    "t2m_range": (0.0, 40.0),
    "t2mdew": (-40.0, 40.0),
    "prectotcorr": (0.0, 500.0),
    "rh2m": (0.0, 100.0),
    "ws2m": (0.0, 60.0),
    "ws2m_max": (0.0, 80.0),
    "wd2m": (0.0, 360.0),
    "ps": (60.0, 110.0),
    "qv2m": (0.0, 40.0),
    "allsky_sfc_sw_dwn": (0.0, 40.0),
    "gwettop": (0.0, 1.0),
    "gwetroot": (0.0, 1.0),
    "gwetprof": (0.0, 1.0),
    "evland": (0.0, 40.0),
    "evptrns": (0.0, 40.0),
    "frost_days": (0.0, 1.0),
    "cdd0": (0.0, 40.0),
}

# Precipitation and soil-moisture series are zero-inflated; forward-fill through
# isolated single-day gaps rather than interpolating rain events.
INTERPOLATE_MAX_GAP = 3


@dataclass
class CleanReport:
    site: str
    rows_in: int
    rows_out: int
    cells_in: int
    missing_cells_in: int
    missing_cells_filled: int
    outliers_clipped: int
    duplicate_days: int
    notes: list[str] = field(default_factory=list)
    column_missing: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "site": self.site,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "missing_fraction_in": round(
                self.missing_cells_in / self.cells_in, 6
            )
            if self.cells_in
            else 0.0,
            "missing_cells_filled": self.missing_cells_filled,
            "outliers_clipped": self.outliers_clipped,
            "duplicate_days": self.duplicate_days,
            "columns_with_long_gaps": ";".join(
                f"{name}({count})" for name, count in sorted(self.column_missing.items())
            ),
            "notes": self.notes,
        }


def load_site_frame(path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"date": str})
    frame["date"] = pd.to_datetime(frame["date"], format="%Y%m%d")
    return frame.sort_values("date").reset_index(drop=True)


def _clip_bounds(frame: pd.DataFrame) -> int:
    clipped = 0
    for column, (low, high) in UNIT_BOUNDS.items():
        if column not in frame.columns:
            continue
        series = frame[column]
        below = series < low
        above = series > high
        clipped += int(below.sum() + above.sum())
        frame[column] = series.clip(lower=low, upper=high)
    return clipped


def _fill_gaps(frame: pd.DataFrame) -> tuple[pd.DataFrame, int, dict[str, int]]:
    filled = 0
    long_gaps: dict[str, int] = {}
    index = pd.DatetimeIndex(frame.index)
    full_index = pd.date_range(index.min(), index.max(), freq="D", name=index.name)
    if len(full_index) != len(index):
        frame = frame.reindex(full_index)

    for column in RAW_COLUMNS:
        if column not in frame.columns:
            continue
        series = frame[column]
        missing_before = int(series.isna().sum())
        if missing_before == 0:
            continue

        interpolated = series.interpolate(
            method="linear", limit=INTERPOLATE_MAX_GAP, limit_direction="both"
        )
        interpolated = interpolated.ffill(limit=INTERPOLATE_MAX_GAP)
        interpolated = interpolated.bfill(limit=INTERPOLATE_MAX_GAP)

        filled += int(missing_before - interpolated.isna().sum())
        residual = int(interpolated.isna().sum())
        if residual:
            # A stretch this long is a real gap in the source product (for
            # example POWER solar irradiance before 1984). Keep it as NaN so
            # downstream aggregation can decide, rather than inventing values.
            long_gaps[column] = residual
        frame[column] = interpolated

    return frame, filled, long_gaps


def _drop_incomplete_rows(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["t2m_max", "t2m_min", "prectotcorr", "gwetprof", "evland"]
    present = [column for column in required if column in frame.columns]
    if not present:
        return frame
    return frame.dropna(subset=present)


def _fix_physical_consistency(frame: pd.DataFrame) -> pd.DataFrame:
    if {"t2m_max", "t2m_min"}.issubset(frame.columns):
        swap = frame["t2m_max"] < frame["t2m_min"]
        if swap.any():
            high = frame.loc[swap, "t2m_max"].to_numpy()
            low = frame.loc[swap, "t2m_min"].to_numpy()
            frame.loc[swap, "t2m_max"] = low
            frame.loc[swap, "t2m_min"] = high

    if {"t2m_max", "t2m_min", "t2m"}.issubset(frame.columns):
        frame["t2m"] = frame["t2m"].clip(
            lower=frame["t2m_min"], upper=frame["t2m_max"]
        )

    if {"t2m_max", "t2m_min", "t2m_range"}.issubset(frame.columns):
        frame["t2m_range"] = (frame["t2m_max"] - frame["t2m_min"]).clip(lower=0.0)

    if {"ws2m", "ws2m_max"}.issubset(frame.columns):
        frame["ws2m_max"] = np.maximum(frame["ws2m_max"], frame["ws2m"])

    if {"gwetprof", "gwetroot", "gwettop"}.issubset(frame.columns):
        frame["gwetroot"] = np.maximum(frame["gwetroot"], frame["gwettop"])
        frame["gwetprof"] = np.maximum(frame["gwetprof"], frame["gwetroot"])

    return frame


def clean_site(frame: pd.DataFrame, site: str) -> tuple[pd.DataFrame, CleanReport]:
    rows_in = int(len(frame))
    cells_in = int(frame[RAW_COLUMNS].shape[0] * frame[RAW_COLUMNS].shape[1])
    missing_cells_in = int(frame[RAW_COLUMNS].isna().to_numpy().sum())

    notes: list[str] = []

    frame = frame.copy()
    # Accept both the harvest file (string YYYYMMDD) and a pre-parsed date.
    frame["date"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d", errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date")

    duplicated = int(frame["date"].duplicated(keep="first").sum())
    if duplicated:
        frame = frame[~frame["date"].duplicated(keep="first")]
        notes.append(f"dropped {duplicated} duplicate dates")

    frame = frame.set_index("date")
    numeric = frame[RAW_COLUMNS].apply(pd.to_numeric, errors="coerce")

    outliers = _clip_bounds(numeric)
    numeric, filled, long_gaps = _fill_gaps(numeric)
    numeric = _fix_physical_consistency(numeric)

    before_drop = int(len(numeric))
    numeric = _drop_incomplete_rows(numeric)
    dropped_rows = before_drop - int(len(numeric))
    if dropped_rows:
        notes.append(f"dropped {dropped_rows} rows lacking core variables")
    if long_gaps:
        notes.append(
            "kept NaN for source gaps: "
            + ", ".join(f"{name}={count}" for name, count in sorted(long_gaps.items()))
        )

    meta = frame.loc[numeric.index, ["site", "province", "latitude", "longitude"]]
    numeric = numeric.join(meta)
    numeric.index.name = "date"

    report = CleanReport(
        site=site,
        rows_in=rows_in,
        rows_out=int(len(numeric)),
        cells_in=cells_in,
        missing_cells_in=missing_cells_in,
        missing_cells_filled=filled,
        outliers_clipped=outliers,
        duplicate_days=duplicated,
        notes=notes,
        column_missing=long_gaps,
    )
    return numeric, report
