"""Pest forecast request models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ForecastQuery(BaseModel):
    farm_id: str
    crop: str | None = None


class GrowthStageRequest(BaseModel):
    farm_id: str
    crop: str = Field(..., min_length=1)
    stage: str = Field(..., min_length=1)
