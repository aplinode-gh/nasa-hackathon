"""App control chat validation models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AppControlChatRequest(BaseModel):
    """Minimal JSON chat request shape (multipart chat is parsed separately)."""

    conversationId: str | None = Field(default=None, min_length=1)
    message: str = Field(..., min_length=1, max_length=2000)


class CreateAppControlConversationRequest(BaseModel):
    language: str = Field(default="en", min_length=2, max_length=5)


class RenameAppControlConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


AttachmentType = Literal["image/jpeg", "image/png", "image/webp"]