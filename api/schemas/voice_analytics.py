"""Pydantic schemas for voice analytics dashboard APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TrackEventRequest(BaseModel):
    event_type: str
    organization_id: int
    session_id: str = ""
    workflow_run_id: int = 0
    value: float | None = None
    success: bool | None = None
    language: str = "mixed"
    labels: dict[str, str] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class MetricAggregateSchema(BaseModel):
    metric: str
    count: int = 0
    sum: float = 0.0
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    success_count: int = 0
    failure_count: int = 0


class DashboardSummarySchema(BaseModel):
    organization_id: int
    from_ts: float
    to_ts: float
    generated_at: float
    metrics: dict[str, Any]
    rates: dict[str, float | None] = Field(default_factory=dict)


class TimeseriesPointSchema(BaseModel):
    bucket: str
    metric: str
    count: int
    sum: float
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    success_count: int = 0
    failure_count: int = 0


class EventSchema(BaseModel):
    event_id: str
    event_type: str
    organization_id: int
    session_id: str = ""
    workflow_run_id: int = 0
    timestamp: float
    value: float | None = None
    success: bool | None = None
    language: str = "mixed"
    labels: dict[str, str] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class AnalyticsStatusSchema(BaseModel):
    enabled: bool
    event_ttl_s: int
    max_events_per_org: int
