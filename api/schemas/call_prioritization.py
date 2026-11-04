"""Pydantic schemas for call prioritization APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EnqueueCustomerRequest(BaseModel):
    customer_id: int
    attempt_number: int = 1
    workflow_run_id: int | None = None


class PrioritizeBatchRequest(BaseModel):
    customer_ids: list[int] = Field(..., min_length=1, max_length=500)


class RecordCallOutcomeRequest(BaseModel):
    customer_id: int
    outcome: str
    phone_e164: str | None = None
    attempt_number: int = 1
    workflow_run_id: int | None = None
    duration_s: float | None = None


class PrioritizationScoreSchema(BaseModel):
    customer_id: int
    organization_id: int
    score: float
    tier: str
    likely_payer: bool
    breakdown: dict[str, Any]
    signals: dict[str, Any]


class QueueSnapshotSchema(BaseModel):
    queue_depth: int
    retry_depth: int
    suggested_batch_size: int
    queue: list[dict[str, Any]]
    retries: list[dict[str, Any]]
