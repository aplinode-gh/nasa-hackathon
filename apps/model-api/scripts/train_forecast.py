from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.datasets.signals import INDICATOR_COLUMNS, SEASON_FEATURE_COLUMNS

QUANTILES = (0.1, 0.5, 0.9)
EXCLUDED_FEATURES = {
    # Trend slope columns are recomputed per site and leak the site identity.
    "tmean_c_per_decade",
    "heat_days_35_per_decade",
    "precip_mm_per_decade",
    "soil_moisture_per_decade",
    "frost_days_per_decade",
}

TARGET_LABELS = {
    "target_next_tmean_c": ("mean temperature", "C"),
    "target_next_heat_days_35": ("heat days above 35C", "days"),
    "target_next_precip_total_mm": ("seasonal rainfall", "mm"),
    "target_next_soil_moisture": ("profile soil moisture", "fraction"),
    "target_next_frost_days": ("frost days", "days"),
    "target_next_extreme_rain_days": ("extreme rainfall days", "days"),
    "target_next_vegetation_stress": ("vegetation stress index", "index"),
}

# Each target's same-season counterpart, used as the persistence baseline.
PERSISTENCE_SOURCE = {
    "target_next_tmean_c": "tmean_c",
    "target_next_heat_days_35": "heat_days_35",
    "target_next_precip_total_mm": "precip_total_mm",
    "target_next_soil_moisture": "soil_moisture_profile_mean",
    "target_next_frost_days": "frost_days_min",
    "target_next_extreme_rain_days": "extreme_rain_days",
    "target_next_vegetation_stress": "vegetation_stress_index",
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


def build_design_matrix(
    frame: pd.DataFrame, features: list[str], seasons: list[str]
) -> tuple[np.ndarray, list[str]]:
    """Numeric features plus location and season identifiers.

    The weather features alone cannot tell Punjab from Balochistan, so the
    site coordinates and a season one-hot are part of the design matrix. This
    is what lets one global model answer location-specific questions.
    """
    numeric = frame[features].to_numpy(dtype=np.float32)
    lat = frame["latitude"].to_numpy(dtype=np.float32).reshape(-1, 1)
    lon = frame["longitude"].to_numpy(dtype=np.float32).reshape(-1, 1)

    one_hot = np.zeros((len(frame), len(seasons)), dtype=np.float32)
    season_index = {name: position for position, name in enumerate(seasons)}
    for row, name in enumerate(frame["season"].astype(str)):
        if name in season_index:
            one_hot[row, season_index[name]] = 1.0

    matrix = np.hstack([numeric, lat, lon, one_hot])
    names = features + ["latitude", "longitude"] + [f"season_{s}" for s in seasons]
    return matrix, names


def _fit(train_x: np.ndarray, train_y: np.ndarray, alpha: float) -> xgb.XGBRegressor:
    model = xgb.XGBRegressor(
        objective="reg:quantileerror",
        quantile_alpha=alpha,
        n_estimators=500,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=3,
        reg_lambda=1.0,
        tree_method="hist",
        random_state=42,
    )
    model.fit(train_x, train_y)
    return model


def _conformal_radius(
    q10: np.ndarray,
    q90: np.ndarray,
    observed: np.ndarray,
    target_coverage: float = 0.8,
) -> float:
    """Conformalized quantile regression (CQR) widening.

    Scores each held-out point by how far it falls outside its predicted band,
    then takes the score quantile that restores the nominal coverage.
    """
    scores = np.maximum(q10 - observed, observed - q90)
    return float(np.quantile(scores, target_coverage))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train next-season quantile forecasters")
    parser.add_argument("--data", default="artifacts/clean/training_table.parquet")
    parser.add_argument("--out", default="artifacts/models")
    parser.add_argument("--holdout-from", type=int, default=2018)
    parser.add_argument("--calibration-from", type=int, default=2014)
    parser.add_argument("--shap", action="store_true")
    args = parser.parse_args()

    frame = pd.read_parquet(Path(args.data))
    features = _feature_columns(frame)

    train = frame[frame["year"] < args.calibration_from]
    calibration = frame[
        (frame["year"] >= args.calibration_from) & (frame["year"] < args.holdout_from)
    ]
    valid = frame[frame["year"] >= args.holdout_from]
    if train.empty or valid.empty or calibration.empty:
        raise SystemExit(
            "Split produced an empty slice: "
            f"train={len(train)} calibration={len(calibration)} valid={len(valid)}"
        )

    seasons = sorted(frame["season"].astype(str).unique().tolist())
    train_x, design_names = build_design_matrix(train, features, seasons)
    calibration_x, _ = build_design_matrix(calibration, features, seasons)
    valid_x, _ = build_design_matrix(valid, features, seasons)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics: dict = {
        "holdout_from_year": args.holdout_from,
        "calibration_from_year": args.calibration_from,
        "features": design_names,
        "seasons": seasons,
        "n_train": int(len(train)),
        "n_calibration": int(len(calibration)),
        "n_valid": int(len(valid)),
        "targets": {},
    }

    for target in TARGET_LABELS:
        if target not in frame.columns:
            continue

        train_y = train[target].to_numpy(dtype=np.float32)
        valid_y = valid[target].to_numpy(dtype=np.float32)
        calibration_y = calibration[target].to_numpy(dtype=np.float32)
        keep = np.isfinite(train_y)
        keep_cal = np.isfinite(calibration_y)
        if keep.sum() < 50 or keep_cal.sum() < 20:
            continue

        predictions: dict[float, np.ndarray] = {}
        calibration_predictions: dict[float, np.ndarray] = {}
        median_model: xgb.XGBRegressor | None = None
        for alpha in QUANTILES:
            model = _fit(train_x[keep], train_y[keep], alpha)
            model.save_model(out_dir / f"{target}_q{int(alpha * 100)}.json")
            predictions[alpha] = model.predict(valid_x)
            calibration_predictions[alpha] = model.predict(calibration_x[keep_cal])
            if alpha == 0.5:
                median_model = model

        q10 = predictions[0.1]
        q50 = predictions[0.5]
        q90 = predictions[0.9]

        radius = _conformal_radius(
            calibration_predictions[0.1],
            calibration_predictions[0.9],
            calibration_y[keep_cal],
        )
        q10_cal = q10 - radius
        q90_cal = q90 + radius
        # Widening must never invert a band around the median.
        q10_cal = np.minimum(q10_cal, q50)
        q90_cal = np.maximum(q90_cal, q50)

        label, unit = TARGET_LABELS[target]

        # Persistence baseline: "next season looks like this season". A model
        # that cannot beat this is not adding forecasting value.
        baseline_mae = None
        source = PERSISTENCE_SOURCE.get(target)
        if source and source in valid.columns:
            baseline_mae = round(
                float(
                    mean_absolute_error(
                        valid_y, valid[source].to_numpy(dtype=np.float32)
                    )
                ),
                4,
            )

        metrics["targets"][target] = {
            "label": label,
            "unit": unit,
            "r2": round(float(r2_score(valid_y, q50)), 4),
            "mae": round(float(mean_absolute_error(valid_y, q50)), 4),
            "persistence_mae": baseline_mae,
            "skill_vs_persistence": (
                round(1.0 - float(mean_absolute_error(valid_y, q50)) / baseline_mae, 4)
                if baseline_mae
                else None
            ),
            "interval_coverage_raw": round(
                float(np.mean((valid_y >= q10) & (valid_y <= q90))), 4
            ),
            "interval_coverage_calibrated": round(
                float(np.mean((valid_y >= q10_cal) & (valid_y <= q90_cal))), 4
            ),
            "conformal_radius": round(radius, 6),
            "n_train": int(keep.sum()),
            "n_calibration": int(keep_cal.sum()),
            "n_valid": int(len(valid_y)),
        }

        if args.shap and median_model is not None:
            try:
                import shap

                explainer = shap.TreeExplainer(median_model)
                sample = valid_x[: min(200, len(valid_x))]
                values = np.asarray(explainer.shap_values(sample))
                importance = np.abs(values).mean(axis=0)
                metrics["targets"][target]["shap_importance"] = {
                    name: round(float(score), 6)
                    for name, score in zip(design_names, importance)
                }
            except Exception as exc:  # optional dependency
                metrics["targets"][target]["shap_error"] = str(exc)

    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "feature_spec.json").write_text(
        json.dumps(features, indent=2), encoding="utf-8"
    )
    (out_dir / "target_spec.json").write_text(
        json.dumps(TARGET_LABELS, indent=2), encoding="utf-8"
    )
    calibration = {
        target: details["conformal_radius"]
        for target, details in metrics["targets"].items()
        if "conformal_radius" in details
    }
    (out_dir / "calibration.json").write_text(
        json.dumps(calibration, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
