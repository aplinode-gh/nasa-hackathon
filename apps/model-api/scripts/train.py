from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score

from app.datasets.schema import FEATURE_COLUMNS, TARGET_COLUMNS

QUANTILES = (0.1, 0.5, 0.9)


def _read(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def _fit(train_x: np.ndarray, train_y: np.ndarray, alpha: float) -> xgb.XGBRegressor:
    model = xgb.XGBRegressor(
        objective="reg:quantileerror",
        quantile_alpha=alpha,
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        tree_method="hist",
        random_state=42,
    )
    model.fit(train_x, train_y)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train quantile surrogate models")
    parser.add_argument("--data", default="artifacts/dataset.parquet")
    parser.add_argument("--out", default="artifacts")
    parser.add_argument("--holdout-site", default=None)
    parser.add_argument("--shap", action="store_true")
    args = parser.parse_args()

    frame = _read(Path(args.data))
    features = [name for name in FEATURE_COLUMNS if name in frame.columns]
    if not features:
        raise SystemExit("No feature columns found in dataset.")

    sites = sorted(frame["site"].unique().tolist())
    holdout = args.holdout_site or sites[-1]
    train = frame[frame["site"] != holdout]
    valid = frame[frame["site"] == holdout]
    if valid.empty or train.empty:
        raise SystemExit(f"Invalid split for holdout site '{holdout}'.")

    train_x = train[features].to_numpy(dtype=float)
    valid_x = valid[features].to_numpy(dtype=float)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics: dict = {"holdout_site": holdout, "features": features, "targets": {}}

    for target in TARGET_COLUMNS:
        if target not in frame.columns:
            continue
        train_y = train[target].to_numpy(dtype=float)
        valid_y = valid[target].to_numpy(dtype=float)
        predictions: dict[float, np.ndarray] = {}
        best_model = None

        for alpha in QUANTILES:
            model = _fit(train_x, train_y, alpha)
            model.save_model(out_dir / f"{target}_q{int(alpha * 100)}.json")
            predictions[alpha] = model.predict(valid_x)
            if alpha == 0.5:
                best_model = model

        p50 = predictions[0.5]
        metrics["targets"][target] = {
            "r2": round(float(r2_score(valid_y, p50)), 4),
            "mae": round(float(mean_absolute_error(valid_y, p50)), 4),
            "interval_coverage": round(
                float(np.mean((valid_y >= predictions[0.1]) & (valid_y <= predictions[0.9]))), 4
            ),
            "n_train": int(len(train_y)),
            "n_valid": int(len(valid_y)),
        }

        if args.shap and best_model is not None:
            try:
                import shap

                explainer = shap.TreeExplainer(best_model)
                sample = valid_x[: min(200, len(valid_x))]
                values = np.asarray(explainer.shap_values(sample))
                importance = np.abs(values).mean(axis=0)
                metrics["targets"][target]["shap_importance"] = {
                    name: round(float(score), 6) for name, score in zip(features, importance)
                }
            except Exception as exc:  # pragma: no cover - optional dependency path
                metrics["targets"][target]["shap_error"] = str(exc)

    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "feature_spec.json").write_text(json.dumps(features, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
