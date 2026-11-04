"""Pydantic schemas for call reliability APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReliabilityStatusSchema(BaseModel):
    enabled: bool
    max_retries: int
    retry_base_delay_s: float
    event_ttl_s: int
    dlq_ttl_s: int
    ws_checkpoint_ttl_s: int
    features: list[str] = Field(default_factory=list)


class FailureSummarySchema(BaseModel):
    organization_id: int
    days: int
    totals: dict[str, int] = Field(default_factory=dict)
    recent_failures: list[dict[str, Any]] = Field(default_factory=list)


class ReplayResultSchema(BaseModel):
    replayed: int
    failed: int
    skipped: int
    total: int


class RecordFailureRequest(BaseModel):
    organization_id: int
    reason: str
    workflow_run_id: int = 0
    session_id: str = ""
    schedule_retry: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
