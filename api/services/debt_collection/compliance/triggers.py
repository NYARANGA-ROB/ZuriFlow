"""Escalation triggers combining compliance violations and conversation risk."""

from __future__ import annotations

from api.services.debt_collection.compliance.types import (
    ComplianceViolation,
    ComplianceViolationType,
    SpeakerRole,
    ViolationSeverity,
)
from api.services.debt_collection.escalation import (
    DebtEscalationRules,
    EscalationDecision,
    get_debt_escalation_rules,
)
from api.services.debt_collection.types import DebtCollectionSession, EscalationRisk


class ComplianceEscalationTriggers:
    """Merge compliance signals with existing debt escalation rules."""

    def __init__(
        self,
        *,
        base_rules: DebtEscalationRules | None = None,
        agent_violation_burst: int = 2,
    ) -> None:
        self._base = base_rules or get_debt_escalation_rules()
        self._agent_violation_burst = agent_violation_burst

    def assess(
        self,
        session: DebtCollectionSession,
        *,
        transcript: str = "",
        inbound_violations: list[ComplianceViolation] | None = None,
        outbound_violations: list[ComplianceViolation] | None = None,
        intent: str = "",
        sentiment_score: float | None = None,
    ) -> EscalationDecision:
        decision = self._base.assess(
            session,
            transcript=transcript,
            intent=intent,
            sentiment_score=sentiment_score,
        )
        inbound = inbound_violations or []
        outbound = outbound_violations or []

        reasons: list[str] = []
        if decision.reason and decision.reason != "none":
            reasons.append(decision.reason)
        risk = decision.risk

        for violation in inbound:
            if violation.speaker != SpeakerRole.CUSTOMER:
                continue
            if violation.violation_type == ComplianceViolationType.CUSTOMER_ABUSIVE:
                reasons.append("customer_abusive_language")
                risk = EscalationRisk.CRITICAL
            elif violation.violation_type == ComplianceViolationType.CUSTOMER_LEGAL_THREAT:
                reasons.append("customer_legal_threat")
                risk = self._higher(risk, EscalationRisk.HIGH)

        agent_blocks = [
            v
            for v in outbound
            if v.speaker == SpeakerRole.AGENT
            and v.severity in (ViolationSeverity.BLOCK, ViolationSeverity.CRITICAL)
        ]
        if agent_blocks:
            session.variables["agent_compliance_blocks"] = int(
                session.variables.get("agent_compliance_blocks", 0)
            ) + len(agent_blocks)
            reasons.append("agent_compliance_violation")
            if session.variables["agent_compliance_blocks"] >= self._agent_violation_burst:
                reasons.append("repeated_agent_compliance_failure")
                risk = self._higher(risk, EscalationRisk.HIGH)

        session.escalation_risk = risk
        should = decision.should_escalate or risk in (
            EscalationRisk.HIGH,
            EscalationRisk.CRITICAL,
        )
        queue = (
            "collections_manager"
            if risk == EscalationRisk.CRITICAL
            else decision.queue
        )
        return EscalationDecision(
            should_escalate=should,
            risk=risk,
            reason=reasons[0] if reasons else "none",
            queue=queue,
        )

    @staticmethod
    def _higher(a: EscalationRisk, b: EscalationRisk) -> EscalationRisk:
        order = (
            EscalationRisk.LOW,
            EscalationRisk.MEDIUM,
            EscalationRisk.HIGH,
            EscalationRisk.CRITICAL,
        )
        return a if order.index(a) >= order.index(b) else b


_triggers: ComplianceEscalationTriggers | None = None


def get_compliance_escalation_triggers() -> ComplianceEscalationTriggers:
    global _triggers
    if _triggers is None:
        _triggers = ComplianceEscalationTriggers()
    return _triggers
