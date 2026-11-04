from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VoiceAnalyticsEventType(str, Enum):
    PAYMENT_SUCCESS = "payment_success"
    WHATSAPP_DELIVERY = "whatsapp_delivery"
    ESCALATION = "escalation"
    INTERRUPTION = "interruption"
    RESPONSE_LATENCY = "response_latency"
    CUSTOMER_SENTIMENT = "customer_sentiment"
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    # Debt collection workflow
    PAYMENT_COMMITMENT = "payment_commitment"
    NEGOTIATION_OFFER = "negotiation_offer"
    INSTALLMENT_SCHEDULED = "installment_scheduled"
    DEBT_ESCALATION_RISK = "debt_escalation_risk"
    REPAYMENT_COLLECTED = "repayment_collected"
    # Call prioritization
    CALL_PRIORITY_SCORED = "call_priority_scored"
    CALL_PRIORITY_QUEUED = "call_priority_queued"
    CALL_RETRY_SCHEDULED = "call_retry_scheduled"
    CALL_OUTCOME_RECORDED = "call_outcome_recorded"
    # Voice campaigns
    CAMPAIGN_EVENT = "campaign_event"
    # Debt collection compliance
    COMPLIANCE_VIOLATION = "compliance_violation"
    COMPLIANCE_BLOCKED = "compliance_blocked"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class VoiceAnalyticsEvent:
    event_type: VoiceAnalyticsEventType
    organization_id: int
    session_id: str = ""
    workflow_run_id: int = 0
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    value: float | None = None
    success: bool | None = None
    language: str = "mixed"
    labels: dict[str, str] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "organization_id": self.organization_id,
            "session_id": self.session_id,
            "workflow_run_id": self.workflow_run_id,
            "timestamp": self.timestamp,
            "value": self.value,
            "success": self.success,
            "language": self.language,
            "labels": dict(self.labels),
            "properties": dict(self.properties),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceAnalyticsEvent:
        return cls(
            event_id=str(data.get("event_id", uuid.uuid4())),
            event_type=VoiceAnalyticsEventType(data["event_type"]),
            organization_id=int(data["organization_id"]),
            session_id=str(data.get("session_id", "")),
            workflow_run_id=int(data.get("workflow_run_id", 0)),
            timestamp=float(data.get("timestamp", time.time())),
            value=float(data["value"]) if data.get("value") is not None else None,
            success=data.get("success") if "success" in data else None,
            language=str(data.get("language", "mixed")),
            labels=dict(data.get("labels") or {}),
            properties=dict(data.get("properties") or {}),
        )


@dataclass
class MetricAggregate:
    metric: str
    count: int = 0
    sum_value: float = 0.0
    min_value: float | None = None
    max_value: float | None = None
    success_count: int = 0
    failure_count: int = 0

    def observe(self, *, value: float | None = None, success: bool | None = None) -> None:
        self.count += 1
        if value is not None:
            self.sum_value += value
            self.min_value = value if self.min_value is None else min(self.min_value, value)
            self.max_value = value if self.max_value is None else max(self.max_value, value)
        if success is True:
            self.success_count += 1
        elif success is False:
            self.failure_count += 1

    @property
    def avg_value(self) -> float | None:
        if self.count == 0 or self.sum_value == 0.0:
            return None
        numeric = sum(1 for _ in range(self.count) if True)
        if self.sum_value and self.count:
            return self.sum_value / max(1, self.count)
        return None

    def to_dict(self) -> dict[str, Any]:
        avg = self.avg_value
        return {
            "metric": self.metric,
            "count": self.count,
            "sum": round(self.sum_value, 4),
            "avg": round(avg, 4) if avg is not None else None,
            "min": round(self.min_value, 4) if self.min_value is not None else None,
            "max": round(self.max_value, 4) if self.max_value is not None else None,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }
