"""Pydantic schemas for AI business call analytics APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BusinessAnalyticsStatusSchema(BaseModel):
    enabled: bool
    kpis: list[dict[str, Any]] = Field(default_factory=list)


class KpiValueSchema(BaseModel):
    name: str
    value: float | int | None = None
    unit: str = ""
    count: int = 0
    success_count: int = 0
    rate: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessMetricsSchema(BaseModel):
    organization_id: int
    from_ts: float
    to_ts: float
    generated_at: float
    total_calls: int = 0
    kpis: dict[str, KpiValueSchema]
    rates: dict[str, float | None] = Field(default_factory=dict)


class TimeseriesPointSchema(BaseModel):
    bucket: str
    metric: str
    count: int = 0
    sum: float = 0.0
    avg: float | None = None
    success_count: int = 0
    rate: float | None = None


class BusinessReportSchema(BaseModel):
    organization_id: int
    from_ts: float
    to_ts: float
    generated_at: float
    summary: BusinessMetricsSchema
    by_language: dict[str, dict[str, Any]] = Field(default_factory=dict)
    by_day: list[dict[str, Any]] = Field(default_factory=list)
    top_events: list[dict[str, Any]] = Field(default_factory=list)


class AnalyticsSchemaResponse(BaseModel):
    kpis: list[dict[str, Any]]
