"""Request models for advisor chat and conversation endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AdvisorChatRequest(BaseModel):
    conversationId: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=2000)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):  # type: ignore[override]
        # Trim message content before validation where possible.
        if isinstance(obj, dict) and isinstance(obj.get("message"), str):
            obj = {**obj, "message": obj["message"].strip()}
        return super().model_validate(obj, *args, **kwargs)


class CreateConversationRequest(BaseModel):
    language: str = Field(default="en", min_length=2, max_length=5)


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):  # type: ignore[override]
        if isinstance(obj, dict) and isinstance(obj.get("title"), str):
            obj = {**obj, "title": obj["title"].strip()}
        return super().model_validate(obj, *args, **kwargs)
