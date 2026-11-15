from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from PIL import Image
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split

from app.vision.disease_info import explain
from app.vision.features import extract_features

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts"
VISION_DIR = ARTIFACT_DIR / "vision"
VISION_MODEL_PATH = VISION_DIR / "disease_model.joblib"
VISION_META_PATH = VISION_DIR / "disease_meta.json"

DISEASE_LABELS_CSV = Path(__file__).resolve().parents[2] / "datasets/vision/processed/disease/labels.csv"
NASA_LABELS_CSV = Path(__file__).resolve().parents[2] / "datasets/vision/processed/nasa/labels.csv"


@dataclass
class VisionArtifacts:
    model: Any
    classes: list[str]
    meta: dict


def _load_csvs(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for p in paths:
        if p.exists():
            df = pd.read_csv(p)
            df["__source_csv"] = str(p)
            frames.append(df)
    if not frames:
        raise FileNotFoundError("No vision label CSVs found. Run prepare_vision_dataset.py first.")
    out = pd.concat(frames, ignore_index=True)
    # normalize paths
    base = Path(__file__).resolve().parents[2]
    def _fix(p: str) -> str:
        path = Path(p)
        if not path.is_absolute():
            path = (base / p).resolve()
        return str(path)
    if "output_path" in out.columns:
        out["output_path"] = out["output_path"].astype(str).map(_fix)
    if "label" not in out.columns:
        raise ValueError("labels.csv must contain a 'label' column")
    out = out[out["output_path"].map(lambda x: Path(x).exists())].copy()
    out["label"] = out["label"].astype(str)
    return out


def train_vision_model(
    label_csvs: list[Path] | None = None,
    out_dir: Path | None = None,
    test_size: float = 0.25,
    random_state: int = 42,
) -> dict:
    csvs = label_csvs or [DISEASE_LABELS_CSV, NASA_LABELS_CSV]
    df = _load_csvs([Path(p) for p in csvs])
    # ensure each class has enough samples for split; if tiny, keep all in train
    counts = df["label"].value_counts()
    keep = counts[counts >= 2].index
    df = df[df["label"].isin(keep)].copy()
    if df.empty:
        raise ValueError("No valid labeled images found for training.")

    X = np.stack([extract_features(p) for p in df["output_path"].tolist()], axis=0)
    y = df["label"].to_numpy()

    stratify = y if (pd.Series(y).value_counts().min() >= 2 and len(set(y)) > 1) else None
    if stratify is not None and len(df) >= 10:
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify
        )
    else:
        Xtr, ytr = X, y
        Xte, yte = X, y

    clf = HistGradientBoostingClassifier(
        max_depth=6,
        learning_rate=0.08,
        max_iter=200,
        random_state=random_state,
    )
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    proba = clf.predict_proba(Xte)
    acc = float(accuracy_score(yte, pred))
    f1 = float(f1_score(yte, pred, average="weighted"))
    labels_sorted = sorted(df["label"].unique().tolist())
    report = classification_report(yte, pred, output_dict=True, zero_division=0)

    out = Path(out_dir) if out_dir else VISION_DIR
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, out / "disease_model.joblib")
    meta = {
        "model_type": "HistGradientBoostingClassifier+color_texture_features",
        "feature": "rgb_hsv_hist_grid_color_texture",
        "classes": clf.classes_.tolist(),
        "num_samples": int(len(df)),
        "num_train": int(len(Xtr)),
        "num_eval": int(len(Xte)),
        "accuracy": acc,
        "f1_weighted": f1,
        "label_counts": df["label"].value_counts().to_dict(),
        "sources": sorted(df["__source_csv"].unique().tolist()),
        "classification_report": report,
        "notes": "Lightweight vision model (no torch/TF). For field-grade disease ID, replace/augment with real labeled leaf photos (e.g. PlantVillage/field) and a deep CNN; NASA imagery contributes context classes.",
    }
    (out / "disease_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _resolve_path() -> Path:
    override = os.getenv("VISION_MODEL_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return VISION_DIR


def load_vision_model() -> VisionArtifacts:
    vdir = _resolve_path()
    model_path = vdir / "disease_model.joblib"
    meta_path = vdir / "disease_meta.json"
    if not model_path.exists():
        raise FileNotFoundError(
            f"Vision model not found at {model_path}. Run scripts/train_vision.py."
        )
    model = joblib.load(model_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    classes = meta.get("classes") or getattr(model, "classes_", []).tolist()
    return VisionArtifacts(model=model, classes=list(classes), meta=meta)


def predict_image(image: Image.Image | str | Path, top_k: int = 3) -> dict:
    art = load_vision_model()
    feats = extract_features(image).reshape(1, -1)
    probs = art.model.predict_proba(feats)[0]
    classes = list(getattr(art.model, "classes_", art.classes))
    pairs = sorted(zip(classes, [float(p) for p in probs]), key=lambda x: x[1], reverse=True)
    best_label, best_conf = pairs[0]
    info = explain(best_label, best_conf, source="multimodal_vision")
    return {
        **info,
        "top_predictions": [
            {"label": lbl, "confidence": round(conf, 4), "info": explain(lbl, conf, source="multimodal_vision")}
            for lbl, conf in pairs[:top_k]
        ],
        "model_meta": {
            "model_type": art.meta.get("model_type"),
            "num_samples": art.meta.get("num_samples"),
            "accuracy": art.meta.get("accuracy"),
            "f1_weighted": art.meta.get("f1_weighted"),
            "classes": classes,
        },
    }


def analyze_nasa_context(image: Image.Image | str | Path) -> dict:
    """Lightweight context read for NASA/field imagery (vegetation/water cues)."""
    if not isinstance(image, Image.Image):
        image = Image.open(image)
    im = image.convert("RGB").resize((256, 256))
    arr = np.asarray(im, dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    ndvi_proxy = float(((g - r) / (g + r + 1e-6)).mean())
    green_ratio = float((g / (r + g + b + 1e-6)).mean())
    brightness = float(arr.mean())
    # heuristics
    cues = []
    if ndvi_proxy > 0.05 and green_ratio > 0.36:
        cues.append("Higher greenness signal: vegetation/crop cover likely present.")
    elif ndvi_proxy < -0.02:
        cues.append("Lower greenness signal: sparse vegetation, bare soil, or water-dominant pixels possible.")
    else:
        cues.append("Moderate greenness signal: mixed vegetation/soil conditions.")
    if brightness < 0.25:
        cues.append("Darker scene: cloud shadow, water, or dense canopy possible.")
    elif brightness > 0.7:
        cues.append("Bright scene: bare soil/sand, clouds, or high-reflectance surfaces possible.")
    return {
        "source_type": "nasa_or_field_context",
        "indices": {
            "ndvi_proxy": round(ndvi_proxy, 4),
            "green_ratio": round(green_ratio, 4),
            "brightness": round(brightness, 4),
        },
        "cues": cues,
        "note": "Proxy indices from RGB imagery (not calibrated satellite NDVI). Use NASA MODIS/VIIRS/SMAP/GPM products for quantitative analysis.",
    }
