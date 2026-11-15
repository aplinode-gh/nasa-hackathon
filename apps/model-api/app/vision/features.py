"""Image feature extraction for lightweight vision classifiers.

Uses NumPy/Pillow only (no torch/tf dependency) so it can run in the existing
model-api environment.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image


def _hist(channel: np.ndarray, bins: int = 16) -> np.ndarray:
    h, _ = np.histogram(channel, bins=bins, range=(0, 256), density=True)
    return h.astype(np.float32)


def _color_stats(arr: np.ndarray) -> np.ndarray:
    # arr: HxWx3 uint8
    feats = []
    for c in range(3):
        ch = arr[:, :, c].astype(np.float32)
        feats.extend([ch.mean() / 255.0, ch.std() / 255.0])
    # RGB histograms
    for c in range(3):
        feats.extend(_hist(arr[:, :, c], bins=16).tolist())
    # simple HSV-ish proxies
    r = arr[:, :, 0].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    b = arr[:, :, 2].astype(np.float32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    diff = mx - mn + 1e-6
    sat = (diff / (mx + 1e-6))
    val = mx / 255.0
    feats.extend([sat.mean(), sat.std(), val.mean(), val.std()])
    # green/red ratios useful for vegetation/disease cues
    feats.append(((g - r) / (g + r + 1e-6)).mean())
    feats.append(((g - b) / (g + b + 1e-6)).mean())
    # texture-ish: gradient magnitude stats
    gy = np.abs(np.diff(arr.astype(np.float32), axis=0)).mean() / 255.0
    gx = np.abs(np.diff(arr.astype(np.float32), axis=1)).mean() / 255.0
    feats.extend([gx, gy, gx + gy])
    return np.array(feats, dtype=np.float32)


def extract_features(image: Image.Image | str | Path, size: int = 128) -> np.ndarray:
    if not isinstance(image, Image.Image):
        image = Image.open(image)
    image = image.convert("RGB").resize((size, size), getattr(Image, "Resampling", Image).BILINEAR)
    arr = np.asarray(image, dtype=np.uint8)
    # global + 2x2 grid features to capture lesion locality
    parts = [arr]
    h, w = arr.shape[:2]
    h2, w2 = h // 2, w // 2
    parts.extend([arr[:h2, :w2], arr[:h2, w2:], arr[h2:, :w2], arr[h2:, w2:]])
    vecs = [_color_stats(p) for p in parts]
    return np.concatenate(vecs, axis=0).astype(np.float32)


def batch_features(paths: Iterable[str | Path], size: int = 128) -> np.ndarray:
    feats = [extract_features(p, size=size) for p in paths]
    if not feats:
        return np.zeros((0, 0), dtype=np.float32)
    return np.stack(feats, axis=0)
