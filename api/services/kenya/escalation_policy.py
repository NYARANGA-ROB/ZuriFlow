"""Escalation policy for Kenyan conversational intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from api.services.kenya.session import KenyaIntelligenceSession
from api.services.kenyan_intent.types import BusinessIntent

_FRUSTRATION = (
    "stupid",
    "useless",
    "idiot",
    "shut up",
    "angry",
    "frustrated",
    "mpumbavu",
    "nimechoka",
    "sijaelewa",
    "you are not helping",
    "speak to a human",
    "nataka mtu",
    "customer care",
)

_SENSITIVE = (
    "fraud",
    "stolen",
    "lawyer",
    "police",
    "national id",
    "kitambulisho",
    "dispute",
    "charged twice",
    "nimeibiwa",
)


@dataclass(frozen=True)
class EscalationDecision:
    escalate: bool
    reason: str
    risk_level: str
    package: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "escalate": self.escalate,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "package": self.package,
        }


def evaluate_escalation(
    *,
    session: KenyaIntelligenceSession,
    raw: str,
    intent: BusinessIntent | None,
    language: str,
    entities: dict[str, Any],
    confidence_action: str,
    workflow_state: dict[str, Any] | None = None,
) -> EscalationDecision:
    lowered = raw.lower()
    reasons: list[str] = []
    risk = "medium"

    if intent == BusinessIntent.ESCALATION or any(
        p in lowered
        for p in (
            "speak to a human",
            "talk to someone",
            "nataka mtu",
            "customer care",
            "transfer me",
        )
    ):
        reasons.append("explicit_human_request")
        risk = "high"
    if session.low_confidence_streak >= 2 or session.clarification_count >= 3:
        reasons.append("repeated_misunderstanding")
    if any(w in lowered for w in _FRUSTRATION):
        reasons.append("frustrated_customer")
        risk = "high"
    if any(w in lowered for w in _SENSITIVE) or intent == BusinessIntent.COMPLAINT:
        reasons.append("sensitive_or_dispute")
        risk = "high"
    if confidence_action == "block_financial" and session.low_confidence_streak >= 1:
        reasons.append("financial_dispute_risk")
        risk = "high"

    if not reasons:
        return EscalationDecision(False, "none", "low", {})

    reason = ",".join(reasons)
    package = {
        "conversation_summary": " | ".join(session.raw_turns[-6:]),
        "detected_language": language,
        "customer_intent": intent.value if intent else "unknown",
        "entities": entities,
        "previous_attempts": {
            "clarifications": session.clarification_count,
            "failed_recognition": session.failed_recognition_count,
            "intents": list(session.last_intents[-8:]),
        },
        "workflow_state": workflow_state or {},
        "code_switches": session.switch_count,
    }
    return EscalationDecision(True, reason, risk, package)
