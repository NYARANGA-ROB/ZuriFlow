"""Pydantic schemas for Kenyan realtime intent detection API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    is_partial: bool = False


class RouteRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    is_partial: bool = False


class ClassificationResultSchema(BaseModel):
    intent: str
    confidence: float
    slots: dict[str, str] = Field(default_factory=dict)
    language: str
    matched_phrases: list[str] = Field(default_factory=list)
    normalized_text: str = ""
    original_text: str = ""
    latency_ms: float = 0.0
    is_partial: bool = False


class RouteDecisionSchema(BaseModel):
    action: str
    intent: str
    confidence: float
    priority: int
    reason: str
    slots: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassifyResponse(BaseModel):
    result: ClassificationResultSchema
    route: RouteDecisionSchema
    enabled: bool


class SessionSnapshotSchema(BaseModel):
    session_id: str
    current_intent: str
    confidence: float
    slots: dict[str, str] = Field(default_factory=dict)
    history: list[str] = Field(default_factory=list)
    interrupted: bool = False
    language: str = "mixed"
    last_result: ClassificationResultSchema | None = None
    last_route: RouteDecisionSchema | None = None


class InterruptRequest(BaseModel):
    partial_text: str = ""


class StatusSchema(BaseModel):
    enabled: bool
    use_normalization: bool
    partial_confidence_threshold: float
    route_confidence_threshold: float
