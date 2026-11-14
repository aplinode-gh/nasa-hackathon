"""Disease detection request models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CreateDetectChatRequest(BaseModel):
    scanId: Optional[str] = None


class DetectChatRequest(BaseModel):
    chatId: str
    message: str = Field(..., min_length=1)


class SaveScanRequest(BaseModel):
    scanId: str
    farmId: str
