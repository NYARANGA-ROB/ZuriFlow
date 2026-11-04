"""Types for debt collection compliance guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SpeakerRole(str, Enum):
    AGENT = "agent"
    CUSTOMER = "customer"


class ViolationSeverity(str, Enum):
    WARN = "warn"
    BLOCK = "block"
    CRITICAL = "critical"


class ComplianceViolationType(str, Enum):
    ABUSIVE_LANGUAGE = "abusive_language"
    ILLEGAL_THREAT = "illegal_threat"
    AGGRESSIVE_NEGOTIATION = "aggressive_negotiation"
    MISSING_POLITE_ALTERNATIVE = "missing_polite_alternative"
    HARASSMENT = "harassment"
    CUSTOMER_ABUSIVE = "customer_abusive"
    CUSTOMER_LEGAL_THREAT = "customer_legal_threat"


@dataclass(frozen=True)
class ComplianceViolation:
    violation_type: ComplianceViolationType
    severity: ViolationSeverity
    rule_id: str
    matched_pattern: str
    speaker: SpeakerRole
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "rule_id": self.rule_id,
            "matched_pattern": self.matched_pattern,
            "speaker": self.speaker.value,
            "message": self.message,
        }


@dataclass
class ModerationResult:
    allowed: bool
    text: str
    original_text: str
    speaker: SpeakerRole
    violations: list[ComplianceViolation] = field(default_factory=list)
    filtered: bool = False
    used_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "text": self.text,
            "original_text": self.original_text,
            "speaker": self.speaker.value,
            "violations": [v.to_dict() for v in self.violations],
            "filtered": self.filtered,
            "used_fallback": self.used_fallback,
        }


@dataclass
class ComplianceAuditEntry:
    session_id: str
    organization_id: int
    speaker: SpeakerRole
    action: str
    violations: list[ComplianceViolation]
    original_text: str
    final_text: str
    workflow_run_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "speaker": self.speaker.value,
            "action": self.action,
            "violations": [v.to_dict() for v in self.violations],
            "original_text": self.original_text,
            "final_text": self.final_text,
            "workflow_run_id": self.workflow_run_id,
            "metadata": dict(self.metadata),
        }
