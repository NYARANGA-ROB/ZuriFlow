"""Pydantic schemas for platform events API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlatformEventStatusSchema(BaseModel):
    enabled: bool
    registered_handlers: list[str]


class PublishEventRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    idempotency_key: str | None = None
    route_async: bool = True


class PublishEventResponse(BaseModel):
    published: bool
    event_id: str | None = None
    db_id: int | None = None
    deduplicated: bool = False
    reason: str | None = None


class PlatformEventSchema(BaseModel):
    event_id: str
    event_type: str
    organization_id: int | None
    source: str
    correlation_id: str | None
    payload: dict[str, Any]
    created_at: str | None = None


class ReplayResultSchema(BaseModel):
    replayed: int
    failed: int
    total: int
    reason: str | None = None


class ObservabilitySnapshotSchema(BaseModel):
    organization_id: int
    counters: dict[str, int]
    last_published_at: float | None = None
