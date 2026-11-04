"""Escalation rules for risky debt collection conversations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from api.services.debt_collection.types import DebtCollectionSession, EscalationRisk

ABUSIVE_PATTERNS = re.compile(
    r"\b(stupid|idiot|thief|conman|fraud|shut up|go away|nonsense|"
    r"mpumbavu|mjinga|mwizi|malaya)\b",
    re.IGNORECASE,
)

LEGAL_THREAT_PATTERNS = re.compile(
    r"\b(lawyer|sue|court|police|report you|ombudsman|central bank|"
    r"wakili|mahakama|polisi|barua ya wakili)\b",
    re.IGNORECASE,
)

REFUSAL_PATTERNS = re.compile(
    r"\b(won't pay|cannot pay|not paying|hakuna pesa|sitaki kulipa|"
    r"siwezi kulipa|no money|maybe next month)\b",
    re.IGNORECASE,
)

_RISK_ORDER = (
    EscalationRisk.LOW,
    EscalationRisk.MEDIUM,
    EscalationRisk.HIGH,
    EscalationRisk.CRITICAL,
)


def _higher_risk(a: EscalationRisk, b: EscalationRisk) -> EscalationRisk:
    return a if _RISK_ORDER.index(a) >= _RISK_ORDER.index(b) else b


@dataclass(frozen=True)
class EscalationDecision:
    should_escalate: bool
    risk: EscalationRisk
    reason: str
    queue: str = "collections_supervisor"

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_escalate": self.should_escalate,
            "risk": self.risk.value,
            "reason": self.reason,
            "queue": self.queue,
        }


class DebtEscalationRules:
    """Score conversation risk and decide when to escalate to a human."""

    def __init__(
        self,
        *,
        max_refusals: int = 3,
        frustration_threshold: float = 0.75,
        interruption_burst: int = 4,
    ) -> None:
        self._max_refusals = max_refusals
        self._frustration_threshold = frustration_threshold
        self._interruption_burst = interruption_burst

    def assess(
        self,
        session: DebtCollectionSession,
        *,
        transcript: str = "",
        intent: str = "",
        sentiment_score: float | None = None,
    ) -> EscalationDecision:
        reasons: list[str] = []
        risk = EscalationRisk.LOW

        if intent in ("escalation", "human_agent"):
            return EscalationDecision(
                should_escalate=True,
                risk=EscalationRisk.HIGH,
                reason="customer_requested_human",
            )

        text = transcript.lower()
        if ABUSIVE_PATTERNS.search(text):
            reasons.append("abusive_language")
            risk = EscalationRisk.CRITICAL
        if LEGAL_THREAT_PATTERNS.search(text):
            reasons.append("legal_threat")
            risk = _higher_risk(risk, EscalationRisk.HIGH)

        if REFUSAL_PATTERNS.search(text):
            session.refusal_count += 1
        if session.refusal_count >= self._max_refusals:
            reasons.append("repeated_refusal")
            risk = _higher_risk(risk, EscalationRisk.MEDIUM)

        if session.interruption_count >= self._interruption_burst:
            reasons.append("interruption_burst")
            risk = _higher_risk(risk, EscalationRisk.MEDIUM)

        if sentiment_score is not None and sentiment_score < -0.6:
            reasons.append("negative_sentiment")
            session.frustration_score = max(session.frustration_score, abs(sentiment_score))
            risk = _higher_risk(risk, EscalationRisk.HIGH)
        elif session.frustration_score >= self._frustration_threshold:
            reasons.append("high_frustration")
            risk = _higher_risk(risk, EscalationRisk.HIGH)

        session.escalation_risk = risk
        should = risk in (EscalationRisk.HIGH, EscalationRisk.CRITICAL) or (
            risk == EscalationRisk.MEDIUM
            and session.refusal_count >= self._max_refusals
            and bool(reasons)
        )
        queue = (
            "collections_manager"
            if risk == EscalationRisk.CRITICAL
            else "collections_supervisor"
        )
        return EscalationDecision(
            should_escalate=should,
            risk=risk,
            reason=reasons[0] if reasons else "none",
            queue=queue,
        )


_rules: DebtEscalationRules | None = None


def get_debt_escalation_rules() -> DebtEscalationRules:
    global _rules
    if _rules is None:
        _rules = DebtEscalationRules()
    return _rules
