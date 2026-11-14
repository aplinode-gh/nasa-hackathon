"""Profit / Loss request models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.services.farms.constants import CROPS, SEASONS, YEAR_OPTIONS

EXPENSE_CATEGORIES = ["seed", "fertilizer", "labor", "irrigation", "transport", "other"]
PROJECTED_CATEGORIES = ["seed", "fertilizer", "labor", "irrigation", "transport"]
SEASON_STATUSES = ["active", "harvested", "completed"]


def _validate_crop(value: str) -> str:
    if value not in CROPS:
        raise ValueError("Please select a valid crop from the list")
    return value


class CreateSeasonRequest(BaseModel):
    farm_id: str = Field(..., min_length=1)
    crop_id: str
    season: str
    year: str
    acres: float = Field(..., gt=0, le=99999)

    @field_validator("crop_id")
    @classmethod
    def _crop(cls, value: str) -> str:
        return _validate_crop(value)

    @field_validator("season")
    @classmethod
    def _season(cls, value: str) -> str:
        if value not in SEASONS:
            raise ValueError("Invalid season")
        return value

    @field_validator("year")
    @classmethod
    def _year(cls, value: str) -> str:
        if value not in YEAR_OPTIONS:
            raise ValueError("Invalid year")
        return value


class UpdateSeasonRequest(BaseModel):
    crop_id: Optional[str] = None
    season: Optional[str] = None
    year: Optional[str] = None
    acres: Optional[float] = Field(None, gt=0, le=99999)
    status: Optional[Literal["active", "harvested", "completed"]] = None
    expected_yield: Optional[float] = Field(None, ge=0)
    expected_price: Optional[float] = Field(None, ge=0)
    actual_yield: Optional[float] = Field(None, ge=0)
    actual_price: Optional[float] = Field(None, ge=0)

    @field_validator("crop_id")
    @classmethod
    def _crop(cls, value):
        return _validate_crop(value) if value is not None else value

    @field_validator("season")
    @classmethod
    def _season(cls, value):
        if value is not None and value not in SEASONS:
            raise ValueError("Invalid season")
        return value

    @field_validator("year")
    @classmethod
    def _year(cls, value):
        if value is not None and value not in YEAR_OPTIONS:
            raise ValueError("Invalid year")
        return value


class CreateExpenseRequest(BaseModel):
    category: Literal["seed", "fertilizer", "labor", "irrigation", "transport", "other"]
    amount: float = Field(..., gt=0)
    date: str
    note: Optional[str] = None

    @field_validator("date")
    @classmethod
    def _date(cls, value: str) -> str:
        from datetime import date

        try:
            date.fromisoformat(value)
        except Exception as exc:
            raise ValueError("Invalid date") from exc
        return value


class UpdateExpenseRequest(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    date: Optional[str] = None
    note: Optional[str] = None

    @field_validator("date")
    @classmethod
    def _date(cls, value):
        if value is None:
            return value
        from datetime import date

        try:
            date.fromisoformat(value)
        except Exception as exc:
            raise ValueError("Invalid date") from exc
        return value


class CreateProjectedCostRequest(BaseModel):
    category: Literal["seed", "fertilizer", "labor", "irrigation", "transport"]
    per_acre_cost_pkr: float = Field(..., gt=0)
