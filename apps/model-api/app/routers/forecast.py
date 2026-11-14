from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.predict import (
    ModelNotTrained,
    answer_question,
    available_sites,
    forecast,
)

router = APIRouter(tags=["forecast"])


class AskRequest(BaseModel):
    site: str = Field(..., description="Pakistan site key, e.g. 'lahore'")
    season: str = Field("rabi", pattern="^(rabi|kharif|annual)$")
    question: str = Field(..., min_length=3)


@router.get("/sites")
def list_sites() -> dict:
    try:
        return {"sites": available_sites()}
    except ModelNotTrained as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/forecast/{site}")
def get_forecast(site: str, season: str = "rabi") -> dict:
    if season not in {"rabi", "kharif", "annual"}:
        raise HTTPException(status_code=422, detail=f"Unknown season: {season}")
    try:
        result = forecast(site, season)
    except ModelNotTrained as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "site": result.site,
        "province": result.province,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "season": result.season,
        "observed_year": result.observed_year,
        "target_year": result.target_year,
        "current_conditions": result.current,
        "predictions": result.predictions,
        "trends": result.trends,
    }


@router.post("/ask")
def ask(request: AskRequest) -> dict:
    try:
        return answer_question(request.site, request.season, request.question)
    except ModelNotTrained as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
