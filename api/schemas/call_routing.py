"""Pydantic schemas for intelligent call routing API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RouteFromIntentRequest(BaseModel):
    session_id: str
    organization_id: int
    workflow_run_id: int = 0
    phone_e164: str = ""
    customer_name: str = "there"
    call_sid: str = ""
    language: str = "mixed"
    text: str = Field(..., min_length=1, max_length=2000)


class CallRoutingPlanSchema(BaseModel):
    destination: str
    queue_name: str
    priority: int
    reason: str
    intent: str
    confidence: float
    language: str
    slots: dict[str, str] = Field(default_factory=dict)
    voice_prompt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CallRoutingResultSchema(BaseModel):
    status: str
    plan: CallRoutingPlanSchema | None = None
    queue_position: int | None = None
    fallback_strategy: str | None = None
    voice_prompt: str = ""
    escalated: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueueEntrySchema(BaseModel):
    session_id: str
    organization_id: int
    queue_name: str
    priority: int
    intent: str
    language: str
    enqueued_at: float
    workflow_run_id: int = 0
    phone_e164: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DequeueRequest(BaseModel):
    organization_id: int
    queue_name: str


class EscalateRequest(BaseModel):
    session_id: str
    organization_id: int
    reason: str
    intent: str = "escalation"
    language: str = "mixed"
    workflow_run_id: int = 0
    phone_e164: str = ""
    call_sid: str = ""
    context: str = ""
    queue_name: str = "human"


class RoutingStatusSchema(BaseModel):
    enabled: bool
    queue_ttl_s: int
    route_confidence_threshold: float
