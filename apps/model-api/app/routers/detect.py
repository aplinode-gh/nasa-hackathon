"""Simple disease detection API.

POST /detect  - upload a leaf/crop image, get disease type + explanation.
GET  /diseases - list supported diseases and guidance.
GET  /detect/info - model status.
"""
from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image

from app.vision.disease_info import explain, list_diseases
from app.vision.model import load_vision_model, predict_image

router = APIRouter(tags=["detect"])


@router.get("/diseases")
def diseases() -> dict[str, Any]:
    return {"diseases": list_diseases()}


@router.get("/detect/info")
def detect_info() -> dict[str, Any]:
    try:
        art = load_vision_model()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "ready": True,
        "model": art.meta.get("model_type"),
        "classes": art.classes,
        "accuracy": art.meta.get("accuracy"),
        "trained_on": art.meta.get("num_samples"),
        "label_counts": art.meta.get("label_counts"),
    }


@router.post("/detect")
async def detect(file: UploadFile = File(...)) -> dict[str, Any]:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload an image file (jpg/png).")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Image is empty.")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be smaller than 10 MB.")
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read image: {exc}") from exc

    try:
        pred = predict_image(image)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Model not trained yet. Run: python scripts/train_vision.py") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Detection failed: {exc}") from exc

    return {
        "disease": pred.get("label"),
        "disease_name": pred.get("disease_name"),
        "disease_type": pred.get("disease_type"),
        "confidence": pred.get("confidence"),
        "severity": pred.get("severity"),
        "crop": pred.get("crop"),
        "description": pred.get("description"),
        "causes": pred.get("causes"),
        "treatment": pred.get("steps"),
        "rescan_timing": pred.get("rescan_timing"),
        "caution": pred.get("caution"),
        "top_predictions": [
            {"disease": t.get("label"), "confidence": t.get("confidence")}
            for t in (pred.get("top_predictions") or [])
        ],
    }
