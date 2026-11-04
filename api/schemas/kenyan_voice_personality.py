"""API schemas for Kenyan voice personality."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VoiceProfileSummarySchema(BaseModel):
    profile_id: str
    style: str
    name: str
    description: str
    icon: str
    domain: str
    tags: list[str]
    default_tone: dict[str, Any]
    multilingual: dict[str, Any]
    tts_mapping: dict[str, Any]


class VoiceProfileDetailSchema(VoiceProfileSummarySchema):
    playback: dict[str, Any]
    system_prompt_overlay: str
    search_keywords: list[str]


class ToneConfigurationSchema(BaseModel):
    emotional_tone: str = "neutral"
    register: str = "professional"
    warmth: float = Field(default=0.5, ge=0.0, le=1.0)
    assertiveness: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy: float = Field(default=0.5, ge=0.0, le=1.0)
    urgency: float = Field(default=0.3, ge=0.0, le=1.0)
    humor: float = Field(default=0.1, ge=0.0, le=1.0)
    max_words_per_sentence: int | None = None
    max_sentences_per_turn: int | None = None


class OrgVoiceSelectionSchema(BaseModel):
    organization_id: int
    profile_id: str | None
    tone: ToneConfigurationSchema | None = None


class PreviewVoiceRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    profile_id: str
    tone: ToneConfigurationSchema | None = None
    was_interrupted: bool = False
    organization_id: int | None = None


class TTSChunkSchema(BaseModel):
    text: str
    pause_after_ms: int


class PreviewVoiceResponse(BaseModel):
    normalized_text: str
    tts_ready_text: str
    chunks: list[TTSChunkSchema]
    pause_before_ms: int
    speed_multiplier: float
    tts_mapping: dict[str, Any]
    system_prompt_overlay: str


class EmotionalToneOptionSchema(BaseModel):
    value: str
    label: str
    description: str


class VoicePersonalityStatusSchema(BaseModel):
    enabled: bool
    profile_count: int
    emotional_tones: list[EmotionalToneOptionSchema]
