from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from PIL import Image

from app.vision.disease_info import explain, list_diseases
from app.vision.model import analyze_nasa_context, load_vision_model, predict_image

# Kept for compatibility; simple top-level /detect and /diseases are also exposed in main.py.
router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("/diseases")
def diseases() -> dict[str, Any]:
    """List known disease types and farmer-facing explanations."""
    return {"diseases": list_diseases()}


@router.get("/model-info")
def model_info() -> dict[str, Any]:
    try:
        art = load_vision_model()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "ready": True,
        "classes": art.classes,
        "meta": {
            "model_type": art.meta.get("model_type"),
            "num_samples": art.meta.get("num_samples"),
            "accuracy": art.meta.get("accuracy"),
            "f1_weighted": art.meta.get("f1_weighted"),
            "label_counts": art.meta.get("label_counts"),
            "notes": art.meta.get("notes"),
        },
    }


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    include_context: bool = Query(True, description="Include NASA/field RGB context cues"),
) -> dict[str, Any]:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Please upload an image file.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded image is empty.")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be smaller than 10 MB.")
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read image: {exc}") from exc

    try:
        pred = predict_image(image)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vision inference failed: {exc}") from exc

    result: dict[str, Any] = {
        "diagnosis": {
            "label": pred.get("label"),
            "disease_name": pred.get("disease_name"),
            "disease_type": pred.get("disease_type"),
            "crop": pred.get("crop"),
            "confidence": pred.get("confidence"),
            "severity": pred.get("severity"),
            "description": pred.get("description"),
            "causes": pred.get("causes"),
            "steps": pred.get("steps"),
            "rescan_timing": pred.get("rescan_timing"),
            "caution": pred.get("caution"),
            "model_source": pred.get("model_source"),
        },
        "top_predictions": pred.get("top_predictions", []),
        "model": pred.get("model_meta", {}),
    }
    if include_context:
        result["image_context"] = analyze_nasa_context(image)
    return result


@router.get("/explain/{label}")
def explain_label(label: str) -> dict[str, Any]:
    return {"disease": explain(label)}
