"""Request models for weather and advisory endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.services.farms.constants import CROPS


class RegisterWeatherRequest(BaseModel):
    farm_id: str = Field(..., min_length=1)
    primary_crop: str
    sowing_date: str
    soil_type: str = Field(..., min_length=1, max_length=40)
    irrigation_method: str = Field(..., min_length=1, max_length=40)

    @field_validator("primary_crop")
    @classmethod
    def validate_crop(cls, v: str) -> str:
        if v not in CROPS:
            raise ValueError("Invalid primary crop")
        return v


class ForecastQuery(BaseModel):
    farm_id: str = Field(..., min_length=1)


class HistoryQuery(BaseModel):
    farm_id: str = Field(..., min_length=1)
    limit: int = Field(default=20, ge=1, le=100)
    cursor: Optional[str] = None


class AcknowledgeRequest(BaseModel):
    action: Literal["acknowledged", "acted_upon"]
