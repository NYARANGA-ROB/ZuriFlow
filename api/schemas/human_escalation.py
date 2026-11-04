"""Pydantic schemas for human escalation operator APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ManualEscalateRequest(BaseModel):
    session_id: str
    reason: str
    intent: str = "escalation"
    language: str = "mixed"
    workflow_run_id: int = 0
    phone_e164: str = ""
    call_sid: str = ""
    customer_name: str = ""
    queue_name: str = "human"
    priority: int = Field(default=50, ge=1, le=100)
    risk_level: str = "medium"


class ClaimEscalationRequest(BaseModel):
    queue_name: str = "human"


class TransferHandoffRequest(BaseModel):
    destination: str | None = None
    timeout_seconds: int = Field(default=30, ge=5, le=120)


class HandoffPackageSchema(BaseModel):
    session_id: str
    organization_id: int
    workflow_run_id: int = 0
    phone_e164: str = ""
    customer_name: str = ""
    customer_id: int | None = None
    intent: str = "escalation"
    reason: str = ""
    language: str = "mixed"
    summary: str = ""
    transcript_excerpt: list[dict[str, Any]] = Field(default_factory=list)
    slots: dict[str, str] = Field(default_factory=dict)
    priority: int = 50
    risk_level: str = "medium"
    call_sid: str = ""
    queue_name: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperatorClaimSchema(BaseModel):
    session_id: str
    organization_id: int
    queue_name: str
    operator_id: int
    claimed_at: float
    handoff: HandoffPackageSchema
