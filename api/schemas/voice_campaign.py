"""Pydantic schemas for voice campaign management APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConfigureCampaignRequest(BaseModel):
    scheduled_start_at: str | None = None
    locale_config: dict[str, Any] | None = None
    throttle: dict[str, Any] | None = None
    contact_timezone_field: str | None = None


class CreateCrmCampaignRequest(BaseModel):
    name: str
    workflow_id: int
    segment: dict[str, Any] = Field(
        default_factory=lambda: {"segment": "all", "min_outstanding": 0, "limit": 500}
    )
    telephony_configuration_id: int | None = None
    rate_limit_per_second: int = Field(default=1, ge=1, le=20)
    max_concurrency: int = Field(default=2, ge=1, le=50)
    schedule_config: dict[str, Any] | None = None
    retry_config: dict[str, Any] | None = None


class ScheduleRetryRequest(BaseModel):
    queued_run_id: int
    reason: str = "no_answer"


class CampaignAnalyticsSchema(BaseModel):
    campaign_id: int
    organization_id: int
    state: str
    total_rows: int
    processed_rows: int
    failed_rows: int
    queue: dict[str, Any]
    answer_rate: float | None = None
    retry_rate: float | None = None
    avg_call_duration_s: float | None = None
    outcomes: dict[str, int] = Field(default_factory=dict)
    locales: dict[str, int] = Field(default_factory=dict)
