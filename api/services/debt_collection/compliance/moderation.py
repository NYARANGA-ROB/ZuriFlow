"""Moderation middleware — inbound/outbound compliance gate."""

from __future__ import annotations

from api.services.debt_collection.compliance.audit import get_compliance_audit_logger
from api.services.debt_collection.compliance.filters import get_conversation_filters
from api.services.debt_collection.compliance.rules import get_compliance_rule_engine
from api.services.debt_collection.compliance.types import (
    ComplianceAuditEntry,
    ModerationResult,
    SpeakerRole,
    ViolationSeverity,
)
from api.services.debt_collection.types import DebtCollectionSession


class ComplianceModerationMiddleware:
    """Filter and audit conversation turns before they reach the customer."""

    def __init__(self) -> None:
        self._rules = get_compliance_rule_engine()
        self._filters = get_conversation_filters()
        self._audit = get_compliance_audit_logger()

    async def process_inbound(
        self,
        session: DebtCollectionSession,
        text: str,
    ) -> ModerationResult:
        violations = self._rules.evaluate(text, speaker=SpeakerRole.CUSTOMER)
        result = ModerationResult(
            allowed=True,
            text=text,
            original_text=text,
            speaker=SpeakerRole.CUSTOMER,
            violations=violations,
        )
        if violations:
            await self._audit.log(
                session,
                ComplianceAuditEntry(
                    session_id=session.session_id,
                    organization_id=session.organization_id,
                    speaker=SpeakerRole.CUSTOMER,
                    action="inbound_flagged",
                    violations=violations,
                    original_text=text,
                    final_text=text,
                    workflow_run_id=session.workflow_run_id,
                ),
            )
        return result

    async def process_outbound(
        self,
        session: DebtCollectionSession,
        text: str,
    ) -> ModerationResult:
        violations = self._rules.evaluate(text, speaker=SpeakerRole.AGENT)
        if not violations:
            return ModerationResult(
                allowed=True,
                text=text,
                original_text=text,
                speaker=SpeakerRole.AGENT,
            )

        filtered_text, was_modified, used_fallback = self._filters.sanitize_agent_text(
            text,
            violations,
            locale=session.locale,
        )
        blocking = any(
            v.severity in (ViolationSeverity.BLOCK, ViolationSeverity.CRITICAL)
            for v in violations
        )
        allowed = not blocking or was_modified or used_fallback

        result = ModerationResult(
            allowed=allowed,
            text=filtered_text,
            original_text=text,
            speaker=SpeakerRole.AGENT,
            violations=violations,
            filtered=was_modified,
            used_fallback=used_fallback,
        )

        await self._audit.log(
            session,
            ComplianceAuditEntry(
                session_id=session.session_id,
                organization_id=session.organization_id,
                speaker=SpeakerRole.AGENT,
                action="outbound_blocked" if blocking else "outbound_warned",
                violations=violations,
                original_text=text,
                final_text=filtered_text,
                workflow_run_id=session.workflow_run_id,
                metadata={
                    "filtered": was_modified,
                    "used_fallback": used_fallback,
                },
            ),
        )
        return result


_middleware: ComplianceModerationMiddleware | None = None


def get_compliance_moderation_middleware() -> ComplianceModerationMiddleware:
    global _middleware
    if _middleware is None:
        _middleware = ComplianceModerationMiddleware()
    return _middleware
