"""Pydantic schemas for Kenyan conversational behavior API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SystemPromptRequest(BaseModel):
    custom_instructions: str = ""
    domain: str = Field(default="general", pattern="^(general|banking|support|telecom)$")
    language_mode: str = Field(default="mixed", pattern="^(english|swahili|mixed)$")


class SystemPromptResponse(BaseModel):
    prompt: str
    enabled: bool


class StyleTransformRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    was_interrupted: bool = False


class StyleTransformResponse(BaseModel):
    normalized: str
    tts_chunks: list[dict]


class RecoveryPromptRequest(BaseModel):
    partial_spoken: str = ""
    language_mode: str = "mixed"


class RecoveryPromptResponse(BaseModel):
    recovery_prefix: str | None
    spoken_recovery: str | None
