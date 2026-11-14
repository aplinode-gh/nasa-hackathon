from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from app.datasets.signals import INDICATOR_COLUMNS, SEASON_FEATURE_COLUMNS

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"
CLEAN_DIR = ARTIFACT_DIR / "clean"
MODEL_DIR = ARTIFACT_DIR / "models"

EXCLUDED_FEATURES = {
    "tmean_c_per_decade",
    "heat_days_35_per_decade",
    "precip_mm_per_decade",
    "soil_moisture_per_decade",
    "frost_days_per_decade",
}

SEASON_LABELS = {
    "rabi": "Rabi (Nov-Apr)",
    "kharif": "Kharif (May-Oct)",
    "annual": "Annual (Jan-Dec)",
}

# Physical bounds per target. Quantile bands are widened for coverage, which
# can push a count of days below zero; those floors are physically impossible.
TARGET_BOUNDS = {
    "target_next_tmean_c": (None, None),
    "target_next_heat_days_35": (0.0, None),
    "target_next_precip_total_mm": (0.0, None),
    "target_next_soil_moisture": (0.0, 1.0),
    "target_next_frost_days": (0.0, None),
    "target_next_extreme_rain_days": (0.0, None),
    "target_next_vegetation_stress": (-1.0, None),
}


class ModelNotTrained(RuntimeError):
    """Raised when the forecasting artifacts have not been generated yet."""


@dataclass
class ForecastResult:
    site: str
    province: str
    latitude: float
    longitude: float
    season: str
    observed_year: int
    target_year: int
    predictions: dict[str, dict[str, float | str | None]]
    current: dict[str, float]
    trends: dict[str, float]


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def _load_state() -> dict:
    training_path = CLEAN_DIR / "training_table.parquet"
    seasonal_path = CLEAN_DIR / "seasonal_features.parquet"
    metrics_path = MODEL_DIR / "metrics.json"
    if not training_path.exists() or not metrics_path.exists():
        raise ModelNotTrained(
            "Model artifacts are missing. Run scripts/prepare_dataset.py then "
            "scripts/train_forecast.py."
        )

    metrics = _read_json(metrics_path, {})
    return {
        "table": pd.read_parquet(training_path),
        # seasonal_features keeps the newest observed season, which has no
        # next-season label yet. It is the right base for a live forecast.
        "observed": pd.read_parquet(seasonal_path)
        if seasonal_path.exists()
        else pd.read_parquet(training_path),
        "trends": pd.read_csv(CLEAN_DIR / "long_term_trends.csv")
        if (CLEAN_DIR / "long_term_trends.csv").exists()
        else pd.DataFrame(),
        "features": metrics.get("features", []),
        "seasons": metrics.get("seasons", ["annual", "kharif", "rabi"]),
        "targets": metrics.get("targets", {}),
        "calibration": _read_json(MODEL_DIR / "calibration.json", {}),
    }


def _feature_columns(frame: pd.DataFrame) -> list[str]:
    candidates = SEASON_FEATURE_COLUMNS + INDICATOR_COLUMNS
    return [
        column
        for column in candidates
        if column in frame.columns
        and column not in EXCLUDED_FEATURES
        and frame[column].notna().any()
    ]


def _design_row(row: pd.Series, features: list[str], seasons: list[str]) -> np.ndarray:
    numeric = row[features].to_numpy(dtype=np.float32)
    lat = np.array([row["latitude"]], dtype=np.float32)
    lon = np.array([row["longitude"]], dtype=np.float32)
    one_hot = np.array(
        [1.0 if str(row["season"]) == season else 0.0 for season in seasons],
        dtype=np.float32,
    )
    return np.concatenate([numeric, lat, lon, one_hot]).reshape(1, -1)


def _quantile_prediction(
    target: str,
    matrix: np.ndarray,
    calibration: dict,
) -> dict[str, float | str | None]:
    outputs: dict[str, float | str | None] = {}
    values: dict[str, float] = {}

    for alpha, key in ((0.1, "p10"), (0.5, "p50"), (0.9, "p90")):
        path = MODEL_DIR / f"{target}_q{int(alpha * 100)}.json"
        if not path.exists():
            return {"p10": None, "p50": None, "p90": None}
        model = xgb.XGBRegressor()
        model.load_model(path)
        values[key] = float(model.predict(matrix)[0])

    radius = float(calibration.get(target, 0.0) or 0.0)
    if radius > 0:
        values["p10"] = values["p10"] - radius
        values["p90"] = values["p90"] + radius
    values["p10"] = min(values["p10"], values["p50"])
    values["p90"] = max(values["p90"], values["p50"])

    low, high = TARGET_BOUNDS.get(target, (None, None))
    for key in values:
        if low is not None:
            values[key] = max(low, values[key])
        if high is not None:
            values[key] = min(high, values[key])

    for key, value in values.items():
        outputs[key] = round(value, 4)
    return outputs


def available_sites() -> list[dict]:
    state = _load_state()
    sites = (
        state["observed"][["site", "province", "latitude", "longitude"]]
        .drop_duplicates(subset="site")
        .sort_values("site")
    )
    return sites.to_dict(orient="records")


def _row_for(site: str, season: str) -> pd.Series:
    state = _load_state()
    observed = state["observed"]
    subset = observed[(observed["site"] == site) & (observed["season"] == season)]
    if subset.empty:
        raise ValueError(f"No observations for site '{site}' and season '{season}'.")
    return subset.sort_values("year").iloc[-1]


def forecast(site: str, season: str) -> ForecastResult:
    state = _load_state()
    row = _row_for(site, season)

    design_features = _feature_columns(state["table"])
    matrix = _design_row(row, design_features, state["seasons"])

    predictions: dict[str, dict[str, float | str | None]] = {}
    for target, spec in state["targets"].items():
        band = _quantile_prediction(target, matrix, state["calibration"])
        band["label"] = spec.get("label", target)
        band["unit"] = spec.get("unit", "")
        band["r2"] = spec.get("r2")
        band["skill_vs_persistence"] = spec.get("skill_vs_persistence")
        predictions[target] = band

    current = {
        "tmean_c": round(float(row["tmean_c"]), 2),
        "heat_days_35": round(float(row["heat_days_35"]), 1),
        "precip_total_mm": round(float(row["precip_total_mm"]), 1),
        "soil_moisture_profile_mean": round(float(row["soil_moisture_profile_mean"]), 3),
        "evaporation_total_mm": round(float(row["evaporation_total_mm"]), 1),
        "frost_days_min": round(float(row["frost_days_min"]), 1),
        "extreme_rain_days": round(float(row["extreme_rain_days"]), 1),
        "vegetation_stress_index": round(float(row["vegetation_stress_index"]), 3),
        "water_balance_mm": round(float(row["water_balance_mm"]), 1),
        "heat_days_45": round(float(row["heat_days_45"]), 1),
    }

    trends: dict[str, float] = {}
    table = state["trends"]
    if not table.empty:
        match = table[(table["site"] == site) & (table["season"] == season)]
        if not match.empty:
            record = match.iloc[0]
            for column in table.columns:
                if column.endswith("per_decade") or column.endswith("1980s_to_2010s"):
                    value = record[column]
                    trends[column] = round(float(value), 3) if pd.notna(value) else None

    return ForecastResult(
        site=site,
        province=str(row["province"]),
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        season=season,
        observed_year=int(row["year"]),
        target_year=int(row["year"]) + 1,
        predictions=predictions,
        current=current,
        trends=trends,
    )


SIGNAL_ALIASES = {
    "temperature": ["temperature", "temp", "heat", "warming", "garmi"],
    "heat_stress": ["heat stress", "heatwave", "heat wave", "hot days", "heat_days_35"],
    "rainfall": ["rain", "rainfall", "precipitation", "barish", "monsoon"],
    "soil_moisture": ["soil moisture", "moisture", "dry soil", "nami"],
    "evaporation": ["evaporation", "evapotranspiration", "et", "water demand"],
    "frost": ["frost", "freeze", "cold", "pala"],
    "extreme_rain": ["extreme rain", "heavy rain", "flood", "cloudburst", "extreme precipitation"],
    "vegetation": ["vegetation", "ndvi", "crop stress", "greenness", "plant stress"],
    "water_trend": ["water trend", "long-term water", "drought", "water availability", "groundwater"],
}


def detect_signals(question: str) -> list[str]:
    text = question.lower()
    matched = []
    for signal_name, aliases in SIGNAL_ALIASES.items():
        if any(alias in text for alias in aliases):
            matched.append(signal_name)
    return matched or ["temperature", "rainfall", "soil_moisture"]


def _fmt(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    # Avoid "-0.0", which reads like a negative measurement.
    if round(value, digits) == 0:
        value = 0.0
    return f"{value:,.{digits}f}"


def answer_question(site: str, season: str, question: str) -> dict:
    result = forecast(site, season)
    signals = detect_signals(question)
    p = result.predictions
    c = result.current

    findings: list[str] = []
    evidence: list[dict] = []

    def band(target: str) -> tuple[float | None, float | None, float | None]:
        entry = p.get(target, {})
        return entry.get("p10"), entry.get("p50"), entry.get("p90")

    if "temperature" in signals or "heat_stress" in signals:
        lo, mid, hi = band("target_next_tmean_c")
        if mid is not None:
            findings.append(
                f"{SEASON_LABELS[season]} mean temperature at {site} was "
                f"{_fmt(c['tmean_c'])} C in {result.observed_year}; next season projects "
                f"near {_fmt(mid)} C (80% band {_fmt(lo)}-{_fmt(hi)} C)."
            )
        lo, mid, hi = band("target_next_heat_days_35")
        if mid is not None:
            findings.append(
                f"Days above 35 C were {_fmt(c['heat_days_35'], 0)} last season, projected "
                f"near {_fmt(mid, 0)} next season (band {_fmt(lo, 0)}-{_fmt(hi, 0)})."
            )
        evidence.append({"signal": "heat_stress", "current": c["heat_days_35"]})

    if "rainfall" in signals:
        lo, mid, hi = band("target_next_precip_total_mm")
        if mid is not None:
            r2 = p.get("target_next_precip_total_mm", {}).get("r2")
            findings.append(
                f"Seasonal rainfall was {_fmt(c['precip_total_mm'], 0)} mm; next season "
                f"projects near {_fmt(mid, 0)} mm (band {_fmt(lo, 0)}-{_fmt(hi, 0)} mm). "
                f"Rainfall skill is limited (R2 {_fmt(r2, 2)}), so treat it as a range, "
                "not a point."
            )

    if "soil_moisture" in signals or "water_trend" in signals:
        lo, mid, hi = band("target_next_soil_moisture")
        if mid is not None:
            findings.append(
                f"Profile soil moisture was {_fmt(c['soil_moisture_profile_mean'], 3)} "
                f"(0-1 fraction); next season projects near {_fmt(mid, 3)} "
                f"(band {_fmt(lo, 3)}-{_fmt(hi, 3)}). This target does not beat a simple "
                "persistence baseline, so the current value is the safer guide."
            )
        trend = result.trends.get("soil_moisture_per_decade")
        if trend is not None:
            findings.append(
                f"Long-term soil moisture trend is {trend:+.4f} per decade over the "
                "1981-2024 record."
            )

    if "evaporation" in signals:
        findings.append(
            f"Seasonal evaporation (water demand) was "
            f"{_fmt(c['evaporation_total_mm'], 0)} mm; water balance (rain minus "
            f"evaporation) was {_fmt(c['water_balance_mm'], 0)} mm."
        )

    if "frost" in signals:
        lo, mid, hi = band("target_next_frost_days")
        if mid is not None:
            observed_frost = c["frost_days_min"]
            if observed_frost <= 0:
                note = (
                    " Persistence is more reliable for frost, so a near-zero count "
                    "is not a frost-free guarantee."
                )
            else:
                note = (
                    f" Persistence is more reliable for frost, so plan around the "
                    f"{_fmt(observed_frost, 0)} days actually observed."
                )
            findings.append(
                f"Frost days were {_fmt(observed_frost, 0)} last season, projected "
                f"near {_fmt(mid, 0)} (band {_fmt(lo, 0)}-{_fmt(hi, 0)}).{note}"
            )
        trend = result.trends.get("frost_days_per_decade")
        if trend is not None:
            findings.append(f"Frost-day trend is {trend:+.2f} days per decade.")

    if "extreme_rain" in signals:
        lo, mid, hi = band("target_next_extreme_rain_days")
        if mid is not None:
            findings.append(
                f"Extreme rainfall days (over 50 mm) were "
                f"{_fmt(c['extreme_rain_days'], 0)}; next season projects near "
                f"{_fmt(mid, 1)} (band {_fmt(lo, 1)}-{_fmt(hi, 1)})."
            )

    if "vegetation" in signals:
        lo, mid, hi = band("target_next_vegetation_stress")
        if mid is not None:
            findings.append(
                f"Vegetation stress index is {_fmt(c['vegetation_stress_index'], 3)} "
                f"(0 = no stress). Next season projects near {_fmt(mid, 3)} "
                f"(band {_fmt(lo, 3)}-{_fmt(hi, 3)}). This uses a heat/aridity proxy, "
                "not satellite NDVI, so it is a screening signal."
            )

    temp_trend = result.trends.get("tmean_c_per_decade")
    if temp_trend is not None:
        direction = "warming" if temp_trend >= 0 else "cooling"
        findings.append(
            f"Long-term temperature trend for this season is {temp_trend:+.3f} C per "
            f"decade ({direction}) over the 1981-2024 NASA POWER record."
        )

    return {
        "site": result.site,
        "province": result.province,
        "season": result.season,
        "season_label": SEASON_LABELS[season],
        "observed_year": result.observed_year,
        "target_year": result.target_year,
        "signals_detected": signals,
        "answer": " ".join(findings),
        "findings": findings,
        "current_conditions": result.current,
        "predictions": result.predictions,
        "trends": result.trends,
        "evidence": evidence,
        "caveats": [
            "Inputs are NASA POWER reanalysis (MERRA-2) at roughly 0.5 degree grid, "
            "not a field-level sensor.",
            "Vegetation stress uses a meteorological proxy because MODIS NDVI is not "
            "ingested in this dataset build.",
            "Forecasts are next-season statistical projections, not physical climate "
            "model output; confirm with local extension services.",
        ],
    }
