from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Season(str, Enum):
    summer = "summer"
    winter = "winter"
    autumn = "autumn"
    spring = "spring"
    rainy = "rainy"
    windy = "windy"


class SoilType(str, Enum):
    sandy = "sandy"
    sandy_loam = "sandy_loam"
    loamy = "loamy"
    clay_loam = "clay_loam"
    clay = "clay"
    silty = "silty"
    saline = "saline"
    rocky = "rocky"
    other = "other"


class IrrigationType(str, Enum):
    rainfed = "rainfed"
    canal = "canal"
    tubewell = "tubewell"
    mixed = "mixed"


class Priorities(BaseModel):
    water: float = Field(default=0.25, ge=0.0, le=1.0)
    income: float = Field(default=0.25, ge=0.0, le=1.0)
    soil_health: float = Field(default=0.25, ge=0.0, le=1.0)
    risk: float = Field(default=0.25, ge=0.0, le=1.0)


class Scenario(BaseModel):
    temp_delta_c: float = 0.0
    precip_delta_pct: float = 0.0


class FieldContext(BaseModel):
    field_id: str | None = None
    lat: float
    lon: float
    soil_type: SoilType
    current_crop: str
    target_season: Season
    irrigation_type: IrrigationType = IrrigationType.mixed


class CompareRotationsRequest(BaseModel):
    field: FieldContext
    candidate_crops: list[str] = Field(default_factory=list)
    priorities: Priorities = Field(default_factory=Priorities)
    scenario: Scenario = Field(default_factory=Scenario)


class OutcomeBand(BaseModel):
    p10: float
    p50: float
    p90: float


class StrategyOutcome(BaseModel):
    water_use_mm: OutcomeBand
    irrigation_need_mm: OutcomeBand
    relative_yield_index: OutcomeBand
    soil_health: float
    erosion_control: float
    nitrogen_fixation: float
    market_score: float
    pest_break: float


class RotationStrategy(BaseModel):
    strategy_id: str
    label: str
    sequence: list[str]
    is_baseline: bool
    score: float
    outcomes: StrategyOutcome
    evidence: list[str]
    gaps: list[str]
    risks: list[str]
    confidence: str
    data_sources: list[str]


class CompareRotationsResponse(BaseModel):
    field_id: str | None
    strategies: list[RotationStrategy]
    priorities_used: Priorities
