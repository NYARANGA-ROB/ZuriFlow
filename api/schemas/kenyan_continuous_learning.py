"""Kenyan continuous learning API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from api.services.kenyan_continuous_learning.types import FeedbackType


class FeedbackIngestRequest(BaseModel):
    feedback_type: FeedbackType
    payload: Dict[str, Any] = Field(default_factory=dict)
    sample_id: Optional[int] = None


class SubmitLabelRequest(BaseModel):
    label_payload: Dict[str, Any]
    status: str = "approved"
    notes: Optional[str] = None


class StartTrainingRequest(BaseModel):
    targets: Optional[List[str]] = None
    days: int = Field(default=30, ge=1, le=180)
    auto_apply: bool = False


class LearningSummarySchema(BaseModel):
    organization_id: int
    enabled: bool
    targets: List[str]
    samples_recent: int
    label_tasks_pending: int
    training_runs: List[Dict[str, Any]] = Field(default_factory=list)
