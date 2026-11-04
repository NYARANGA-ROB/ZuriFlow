"""Pydantic schemas for Kenyan accent detection API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AccentScoresSchema(BaseModel):
    generic_english: float = Field(..., ge=0.0, le=1.0)
    kenyan_english: float = Field(..., ge=0.0, le=1.0)


class ConfidenceFactorsSchema(BaseModel):
    snr_db: float
    speech_ratio: float
    segment_duration_s: float
    model_entropy: float
    pyannote_used: bool


class AccentPredictionSchema(BaseModel):
    label: str = Field(..., description="generic_english or kenyan_english")
    probability: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    scores: AccentScoresSchema
    factors: ConfidenceFactorsSchema
    is_stable: bool = False
    session_id: str | None = None


class ClassifyPCMRequest(BaseModel):
    pcm_base64: str = Field(..., description="Base64-encoded int16 PCM mono audio")
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    session_id: str | None = None


class ClassifyPCMResponse(BaseModel):
    prediction: AccentPredictionSchema | None
    enabled: bool


class StreamSessionResponse(BaseModel):
    session_id: str
    sample_rate: int


class StreamChunkRequest(BaseModel):
    pcm_base64: str
    sample_rate: int = Field(default=16000, ge=8000, le=48000)


class StreamChunkResponse(BaseModel):
    prediction: AccentPredictionSchema | None
    session_id: str


class StreamResultResponse(BaseModel):
    session_id: str
    prediction: AccentPredictionSchema | None


class AccentStatusResponse(BaseModel):
    enabled: bool
    model_loaded: bool
    pyannote_available: bool
    config: dict[str, Any]
