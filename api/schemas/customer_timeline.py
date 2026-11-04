"""Pydantic schemas for customer timeline API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TimelineEntrySchema(BaseModel):
    id: int
    organization_id: int
    customer_id: int | None
    phone_e164: str
    channel: str
    event_type: str
    title: str
    summary: str | None
    payload: dict[str, Any]
    workflow_run_id: int | None
    conversation_id: int | None
    transaction_id: int | None
    correlation_id: str | None
    journey_state: str | None
    occurred_at: str
    platform_event_id: int | None = None


class CustomerTimelineSchema(BaseModel):
    organization_id: int
    customer_id: int | None
    phone_e164: str
    customer_uuid: str | None
    full_name: str | None
    journey_state: str
    channels_active: list[str]
    entries: list[TimelineEntrySchema]
    entry_count: int


class JourneyStateSchema(BaseModel):
    journey_state: str
    channels_active: list[str] = Field(default_factory=list)
    customer_id: int | None = None
    phone_e164: str | None = None
