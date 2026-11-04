"""Pydantic schemas for conversation quality APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConversationQualityStatusSchema(BaseModel):
    enabled: bool
    model_version: str
    dimensions: List[str]


class DimensionScoreSchema(BaseModel):
    dimension: str
    score: float
    weight: float
    evidence: Dict[str, Any] = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)


class ConversationEvaluationSchema(BaseModel):
    organization_id: int
    workflow_run_id: int
    workflow_id: Optional[int] = None
    model_version: str
    overall_score: float
    dimensions: Dict[str, DimensionScoreSchema]
    metrics: Dict[str, Any] = Field(default_factory=dict)
    regression: Dict[str, Any] = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)
    evaluated_at: Optional[str] = None


class ConversationQualitySummarySchema(BaseModel):
    organization_id: int
    evaluation_count: int
    avg_overall_score: Optional[float] = None
    dimension_averages: Dict[str, float] = Field(default_factory=dict)
    regression_count: int = 0
    recent_regressions: List[Dict[str, Any]] = Field(default_factory=list)
