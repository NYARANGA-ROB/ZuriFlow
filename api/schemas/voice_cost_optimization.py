"""Pydantic schemas for voice cost optimization APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VoiceCostStatusSchema(BaseModel):
    enabled: bool
    prerecorded_enabled: bool = True
    response_cache_enabled: bool = True
    tts_dedup_enabled: bool = True
    token_budgets: dict[str, int] = Field(default_factory=dict)
    prerecorded_keys: list[dict[str, Any]] = Field(default_factory=list)


class CostAnalyticsSchema(BaseModel):
    organization_id: int
    from_ts: float
    to_ts: float
    generated_at: float
    total_sessions: int = 0
    llm_calls: int = 0
    cache_hits: int = 0
    prerecorded_hits: int = 0
    tts_characters: int = 0
    tts_generations_avoided: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_saved: int = 0
    estimated_cost_usd: float = 0.0
    estimated_savings_usd: float = 0.0


class SessionCostSchema(BaseModel):
    found: bool
    session_id: str | None = None
    organization_id: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    llm_calls: int | None = None
    cache_hits: int | None = None
    prerecorded_hits: int | None = None
    tokens_saved: int | None = None


class ResolveTurnRequest(BaseModel):
    text: str
    organization_id: int = 0
    locale: str = "mixed"
    turn_count: int = 0
    intent: str = ""
    intent_confidence: float = 0.0
