"""Pydantic schemas for durable orchestration API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DurableExecutionStatusSchema(BaseModel):
    enabled: bool
    definitions: list[str]


class StartOrchestrationRequest(BaseModel):
    definition_name: str
    orchestration_key: str
    workflow_run_id: int | None = None
    initial_state: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class SignalOrchestrationRequest(BaseModel):
    signal_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class OrchestrationSummarySchema(BaseModel):
    id: int
    organization_id: int
    definition_name: str
    orchestration_key: str
    status: str
    current_step: str
    workflow_run_id: int | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None


class OrchestrationResultSchema(BaseModel):
    orchestration_id: int
    organization_id: int
    definition_name: str
    orchestration_key: str
    status: str
    current_step: str
    state: dict[str, Any]
    error_message: str | None = None


class OrchestrationEventSchema(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any]
    created_at: str | None = None
