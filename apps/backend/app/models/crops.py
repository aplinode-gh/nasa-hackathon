"""Request and query models for crop recommendation endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Season = Literal["summer", "winter", "autumn", "spring", "rainy", "windy"]
SoilType = Literal["sandy", "sandy_loam", "loamy", "clay_loam", "clay", "silty", "saline", "rocky", "other"]
BudgetBracket = Literal["low", "medium", "high", "very_high"]
IrrigationType = Literal["rainfed", "canal", "tubewell", "mixed"]
CropCategory = Literal["staple", "cash", "pulse", "vegetable"]


class CreateCropRecommendationRequest(BaseModel):
    farm_id: str = Field(..., min_length=1)
    target_season: Season
    target_year: int
    soil_type: SoilType
    irrigation_type: IrrigationType
    budget_bracket: BudgetBracket
    regenerate: bool = False

    @field_validator("target_year")
    @classmethod
    def validate_target_year(cls, v: int) -> int:
        current_year = datetime.utcnow().year
        if v < current_year or v > 2035:
            raise ValueError("target_year must be between the current year and 2035")
        return v


class CropCatalogueQuery(BaseModel):
    season: Optional[Season] = None
    category: Optional[CropCategory] = None
    locale: Optional[str] = None


class SaveRecommendationRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1)
