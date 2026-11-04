"""Domain types for Kenyan continuous learning."""

from __future__ import annotations

from enum import Enum


class LearningTarget(str, Enum):
    NORMALIZATION = "normalization"
    INTENT = "intent"
    INTERRUPTION = "interruption"
    RANKING = "ranking"
    GENERAL = "general"


class SampleSource(str, Enum):
    WORKFLOW_RUN = "workflow_run"
    OPERATOR_FEEDBACK = "operator_feedback"
    QUALITY_EVAL = "quality_eval"
    INTENT_LOW_CONFIDENCE = "intent_low_confidence"


class LabelTaskStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class FeedbackType(str, Enum):
    NORMALIZATION_CORRECTION = "normalization_correction"
    INTENT_CORRECTION = "intent_correction"
    INTERRUPTION_NOTE = "interruption_note"
    RANKING_OUTCOME = "ranking_outcome"
    GENERAL = "general"


class TrainingRunStatus(str, Enum):
    QUEUED = "queued"
    COLLECTING = "collecting"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"
    APPLIED = "applied"
