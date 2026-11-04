"""Tests for debt collection compliance guardrails."""

from __future__ import annotations

import asyncio

from api.services.debt_collection.compliance.filters import get_conversation_filters
from api.services.debt_collection.compliance.rules import get_compliance_rule_engine
from api.services.debt_collection.compliance.triggers import ComplianceEscalationTriggers
from api.services.debt_collection.compliance.types import SpeakerRole, ViolationSeverity
from api.services.debt_collection.types import DebtCollectionSession, EscalationRisk


def test_agent_illegal_threat_blocked():
    engine = get_compliance_rule_engine()
    violations = engine.evaluate(
        "Pay now or we will send police to arrest you.",
        speaker=SpeakerRole.AGENT,
    )
    assert any(v.violation_type.value == "illegal_threat" for v in violations)
    assert engine.highest_severity(violations) == ViolationSeverity.BLOCK


def test_agent_abusive_language_blocked():
    engine = get_compliance_rule_engine()
    violations = engine.evaluate("You are a stupid deadbeat.", speaker=SpeakerRole.AGENT)
    assert violations
    assert violations[0].severity == ViolationSeverity.BLOCK


def test_conversation_filter_replaces_threat():
    filters = get_conversation_filters()
    engine = get_compliance_rule_engine()
    text = "Pay now or else we will arrest you."
    violations = engine.evaluate(text, speaker=SpeakerRole.AGENT)
    filtered, modified, used_fallback = filters.sanitize_agent_text(
        text, violations, locale="en"
    )
    assert modified or used_fallback
    assert "arrest" not in filtered.lower()


def test_polite_negotiation_warns_on_ultimatum_without_alternative():
    engine = get_compliance_rule_engine()
    violations = engine.evaluate(
        "You must pay the full amount today.",
        speaker=SpeakerRole.AGENT,
    )
    assert any(v.violation_type.value == "missing_polite_alternative" for v in violations)


def test_customer_abusive_triggers_critical_escalation():
    rules = ComplianceEscalationTriggers()
    session = DebtCollectionSession(session_id="c1", organization_id=1)
    engine = get_compliance_rule_engine()
    inbound_violations = engine.evaluate(
        "you are a stupid thief", speaker=SpeakerRole.CUSTOMER
    )
    decision = rules.assess(
        session,
        transcript="you are a stupid thief",
        inbound_violations=inbound_violations,
    )
    assert decision.risk == EscalationRisk.CRITICAL
    assert decision.should_escalate is True


def test_outbound_moderation_filters_agent_prompt():
    async def _run():
        from api.services.debt_collection.compliance.service import (
            get_compliance_guardrail_service,
        )
        from api.services.debt_collection.engine import get_debt_collection_engine
        from api.services.debt_collection.types import DebtAccount

        engine = get_debt_collection_engine()
        data = await engine.start(
            organization_id=1,
            account=DebtAccount(
                account_id="C1",
                customer_name="Alice",
                phone_e164="+254733333333",
                outstanding_balance=8000.0,
            ),
        )
        session = engine.get_session(data["session_id"])
        assert session is not None
        compliance = get_compliance_guardrail_service()
        result = await compliance.moderate_outbound(
            session,
            "Pay now or else — this is your final warning.",
        )
        assert result.filtered or result.used_fallback
        assert "final warning" not in result.text.lower()
        assert result.violations

    asyncio.run(_run())


def test_engine_escalates_on_customer_abusive_transcript():
    async def _run():
        from api.services.debt_collection.engine import get_debt_collection_engine
        from api.services.debt_collection.types import DebtAccount

        engine = get_debt_collection_engine()
        data = await engine.start(
            organization_id=1,
            account=DebtAccount(
                account_id="C2",
                customer_name="Bob",
                phone_e164="+254744444444",
                outstanding_balance=3000.0,
            ),
        )
        sid = data["session_id"]
        result = await engine.handle_transcript(sid, "you idiot stop calling me")
        assert result["escalation_risk"] in ("critical", "high")

    asyncio.run(_run())
