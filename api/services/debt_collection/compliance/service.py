"""Compliance guardrail service facade."""

from __future__ import annotations

from typing import Any

from api.constants import DEBT_COLLECTION_COMPLIANCE_ENABLED
from api.services.debt_collection.compliance.audit import get_compliance_audit_logger
from api.services.debt_collection.compliance.moderation import (
    get_compliance_moderation_middleware,
)
from api.services.debt_collection.compliance.rules import get_compliance_rule_engine
from api.services.debt_collection.compliance.triggers import (
    get_compliance_escalation_triggers,
)
from api.services.debt_collection.compliance.types import ModerationResult, SpeakerRole
from api.services.debt_collection.escalation import EscalationDecision
from api.services.debt_collection.types import DebtCollectionSession


class ComplianceGuardrailService:
    """Orchestrates moderation, rules, audit, and escalation for debt calls."""

    def __init__(self) -> None:
        self._middleware = get_compliance_moderation_middleware()
        self._rules = get_compliance_rule_engine()
        self._triggers = get_compliance_escalation_triggers()
        self._audit = get_compliance_audit_logger()

    @property
    def enabled(self) -> bool:
        return DEBT_COLLECTION_COMPLIANCE_ENABLED

    async def moderate_inbound(
        self,
        session: DebtCollectionSession,
        text: str,
    ) -> ModerationResult:
        if not self.enabled:
            return ModerationResult(
                allowed=True,
                text=text,
                original_text=text,
                speaker=SpeakerRole.CUSTOMER,
            )
        return await self._middleware.process_inbound(session, text)

    async def moderate_outbound(
        self,
        session: DebtCollectionSession,
        text: str,
    ) -> ModerationResult:
        if not self.enabled:
            return ModerationResult(
                allowed=True,
                text=text,
                original_text=text,
                speaker=SpeakerRole.AGENT,
            )
        return await self._middleware.process_outbound(session, text)

    def assess_escalation(
        self,
        session: DebtCollectionSession,
        *,
        transcript: str = "",
        inbound: ModerationResult | None = None,
        outbound: ModerationResult | None = None,
        intent: str = "",
        sentiment_score: float | None = None,
    ) -> EscalationDecision:
        if not self.enabled:
            from api.services.debt_collection.escalation import get_debt_escalation_rules

            return get_debt_escalation_rules().assess(
                session,
                transcript=transcript,
                intent=intent,
                sentiment_score=sentiment_score,
            )
        return self._triggers.assess(
            session,
            transcript=transcript,
            inbound_violations=inbound.violations if inbound else None,
            outbound_violations=outbound.violations if outbound else None,
            intent=intent,
            sentiment_score=sentiment_score,
        )

    def check_text(self, text: str, *, speaker: SpeakerRole) -> dict[str, Any]:
        violations = self._rules.evaluate(text, speaker=speaker)
        return {
            "speaker": speaker.value,
            "violations": [v.to_dict() for v in violations],
            "highest_severity": (
                self._rules.highest_severity(violations).value
                if violations
                else None
            ),
        }

    async def get_audit_log(
        self,
        session: DebtCollectionSession | None,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if session is not None:
            in_memory = self._audit.list_from_session(session, limit=limit)
            if in_memory:
                return in_memory
        return await self._audit.list_entries(session_id, limit=limit)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "rules": [
                "agent_illegal_threat",
                "agent_abusive_language",
                "agent_aggressive_negotiation",
                "agent_harassment",
                "polite_negotiation",
                "customer_abusive_language",
                "customer_legal_threat",
            ],
            "features": [
                "moderation_middleware",
                "compliance_rule_engine",
                "conversation_filters",
                "audit_logging",
                "escalation_triggers",
            ],
        }


_service: ComplianceGuardrailService | None = None


def get_compliance_guardrail_service() -> ComplianceGuardrailService:
    global _service
    if _service is None:
        _service = ComplianceGuardrailService()
    return _service
