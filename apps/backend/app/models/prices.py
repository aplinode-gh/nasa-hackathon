"""Request models for market price endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GetPricesQuery(BaseModel):
    crop_id: Optional[str] = None
    district: Optional[str] = None
    farm_id: Optional[str] = None
    query: Optional[str] = None
    include_bordering: bool = True


class CreatePriceRequest(BaseModel):
    crop_id: str = Field(..., min_length=1)
    mandi_id: str = Field(..., min_length=1)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    modal_price: float = Field(..., gt=0)
    min_price: float = Field(..., gt=0)
    max_price: float = Field(..., gt=0)
    is_holiday: bool = False


class PredictionQuery(BaseModel):
    crop_id: str = Field(..., min_length=1)
    mandi_id: str = Field(..., min_length=1)


class AlertCreateRequest(BaseModel):
    crop_id: str = Field(..., min_length=1)
    mandi_id: Optional[str] = None
    target_price_pkr: float = Field(..., gt=0)
    status: Literal["active", "paused"] = "active"


class AlertUpdateRequest(BaseModel):
    target_price_pkr: Optional[float] = Field(default=None, gt=0)
    status: Optional[Literal["active", "paused"]] = None


class HistoryQuery(BaseModel):
    crop_id: str = Field(..., min_length=1)
    mandi_id: str = Field(..., min_length=1)
    range: Literal["1M", "3M", "6M", "12M"] = "3M"
