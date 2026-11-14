"""Farm and record Pydantic models."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.services.farms.constants import (
    CROPS,
    IRRIGATION_METHODS,
    RECORD_TYPES,
    SEASONS,
    SOIL_TYPES,
    WEATHER_CONDITIONS,
    YEAR_OPTIONS,
)


def _normalize_district(value: str) -> str:
    v = (value or "").strip()
    if len(v) < 2:
        raise ValueError("Select a valid district")
    return v


class CreateFarmRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    location: str = Field(..., min_length=1)
    district: str
    crops: list[str] = Field(..., min_length=1, max_length=10)
    acres: float = Field(..., gt=0, le=99999)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    primary_crop: Optional[str] = None
    sowing_date: Optional[str] = None
    soil_type: Optional[str] = None
    irrigation_method: Optional[str] = None
    client_uuid: Optional[str] = None

    @field_validator("district")
    @classmethod
    def validate_district(cls, v: str) -> str:
        return _normalize_district(v)

    @field_validator("crops", "primary_crop")
    @classmethod
    def validate_crops(cls, v):
        if v is None:
            return v
        items = v if isinstance(v, list) else [v]
        for item in items:
            if item not in CROPS:
                raise ValueError(f"Invalid crop: {item}")
        return v

    @field_validator("soil_type")
    @classmethod
    def validate_soil(cls, v):
        if v is not None and v not in SOIL_TYPES:
            raise ValueError("Invalid soil type")
        return v

    @field_validator("irrigation_method")
    @classmethod
    def validate_irrigation(cls, v):
        if v is not None and v not in IRRIGATION_METHODS:
            raise ValueError("Invalid irrigation method")
        return v

    @field_validator("sowing_date")
    @classmethod
    def validate_sowing_date(cls, v):
        if v in (None, ""):
            return None
        try:
            date.fromisoformat(v)
        except Exception as e:
            raise ValueError("Invalid date") from e
        return v


class UpdateFarmRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    location: Optional[str] = Field(None, min_length=1)
    district: Optional[str] = None
    crops: Optional[list[str]] = Field(None, min_length=1, max_length=10)
    acres: Optional[float] = Field(None, gt=0, le=99999)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    primary_crop: Optional[str] = None
    sowing_date: Optional[str] = None
    soil_type: Optional[str] = None
    irrigation_method: Optional[str] = None
    growth_stages: Optional[dict[str, Any]] = None
    client_uuid: Optional[str] = None

    @field_validator("district")
    @classmethod
    def validate_district(cls, v):
        return _normalize_district(v) if v is not None else v

    @field_validator("crops", "primary_crop")
    @classmethod
    def validate_crops(cls, v):
        if v is None:
            return v
        items = v if isinstance(v, list) else [v]
        for item in items:
            if item not in CROPS:
                raise ValueError(f"Invalid crop: {item}")
        return v

    @field_validator("soil_type")
    @classmethod
    def validate_soil(cls, v):
        if v is not None and v not in SOIL_TYPES:
            raise ValueError("Invalid soil type")
        return v

    @field_validator("irrigation_method")
    @classmethod
    def validate_irrigation(cls, v):
        if v is not None and v not in IRRIGATION_METHODS:
            raise ValueError("Invalid irrigation method")
        return v

    @field_validator("sowing_date")
    @classmethod
    def validate_sowing_date(cls, v):
        if v in (None, ""):
            return None
        try:
            date.fromisoformat(v)
        except Exception as e:
            raise ValueError("Invalid date") from e
        return v


class CreateRecordRequest(BaseModel):
    farm_id: str
    type: str
    season: str
    year: str
    event_date: str
    title: str = Field(..., min_length=1, max_length=200)
    note: str = Field(..., min_length=1)
    weather_condition: Optional[str] = None
    yield_qty: Optional[float] = Field(None, ge=0)
    labor_cost: Optional[float] = Field(None, ge=0)
    transport_cost: Optional[float] = Field(None, ge=0)
    client_uuid: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in RECORD_TYPES:
            raise ValueError("Invalid record type")
        return v

    @field_validator("season")
    @classmethod
    def validate_season(cls, v):
        if v not in SEASONS:
            raise ValueError("Invalid season")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v):
        if v not in YEAR_OPTIONS:
            raise ValueError("Invalid year")
        return v

    @field_validator("weather_condition")
    @classmethod
    def validate_weather(cls, v):
        if v is not None and v not in WEATHER_CONDITIONS:
            raise ValueError("Invalid weather condition")
        return v

    @field_validator("event_date")
    @classmethod
    def validate_event_date(cls, v):
        try:
            date.fromisoformat(v)
        except Exception as e:
            raise ValueError("Invalid date") from e
        return v


class UpdateRecordRequest(BaseModel):
    type: Optional[str] = None
    season: Optional[str] = None
    year: Optional[str] = None
    event_date: Optional[str] = None
    title: Optional[str] = Field(None, max_length=200)
    note: Optional[str] = None
    weather_condition: Optional[str] = None
    yield_qty: Optional[float] = Field(None, ge=0)
    labor_cost: Optional[float] = Field(None, ge=0)
    transport_cost: Optional[float] = Field(None, ge=0)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v is not None and v not in RECORD_TYPES:
            raise ValueError("Invalid record type")
        return v

    @field_validator("season")
    @classmethod
    def validate_season(cls, v):
        if v is not None and v not in SEASONS:
            raise ValueError("Invalid season")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v):
        if v is not None and v not in YEAR_OPTIONS:
            raise ValueError("Invalid year")
        return v

    @field_validator("weather_condition")
    @classmethod
    def validate_weather(cls, v):
        if v is not None and v not in WEATHER_CONDITIONS:
            raise ValueError("Invalid weather condition")
        return v

    @field_validator("event_date")
    @classmethod
    def validate_event_date(cls, v):
        if v is None:
            return v
        try:
            date.fromisoformat(v)
        except Exception as e:
            raise ValueError("Invalid date") from e
        return v
