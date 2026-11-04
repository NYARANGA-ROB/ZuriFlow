"""Domain types for conversation quality evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


EVALUATION_MODEL_VERSION = "cq-v1"


class QualityDimension(str, Enum):
    RESPONSE_QUALITY = "response_quality"
    INTERRUPTION_HANDLING = "interruption_handling"
    PAYMENT_NEGOTIATION = "payment_negotiation"
    LATENCY = "latency"
    CONVERSATIONAL_NATURALNESS = "conversational_naturalness"
    ESCALATION_CORRECTNESS = "escalation_correctness"


DEFAULT_DIMENSION_WEIGHTS: dict[QualityDimension, float] = {
    QualityDimension.RESPONSE_QUALITY: 0.20,
    QualityDimension.INTERRUPTION_HANDLING: 0.15,
    QualityDimension.PAYMENT_NEGOTIATION: 0.15,
    QualityDimension.LATENCY: 0.20,
    QualityDimension.CONVERSATIONAL_NATURALNESS: 0.15,
    QualityDimension.ESCALATION_CORRECTNESS: 0.15,
}

REGRESSION_DROP_THRESHOLD = 10.0
REGRESSION_MIN_SAMPLE = 5


@dataclass
class DimensionScore:
    dimension: QualityDimension
    score: float
    weight: float
    evidence: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 2),
            "weight": self.weight,
            "evidence": self.evidence,
            "flags": self.flags,
        }


@dataclass
class ConversationEvaluation:
    organization_id: int
    workflow_run_id: int
    workflow_id: int | None
    model_version: str
    overall_score: float
    dimensions: list[DimensionScore]
    metrics: dict[str, Any]
    regression: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "workflow_run_id": self.workflow_run_id,
            "workflow_id": self.workflow_id,
            "model_version": self.model_version,
            "overall_score": round(self.overall_score, 2),
            "dimensions": {d.dimension.value: d.to_dict() for d in self.dimensions},
            "metrics": self.metrics,
            "regression": self.regression,
            "flags": self.flags,
        }
