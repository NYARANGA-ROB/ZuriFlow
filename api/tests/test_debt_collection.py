"""Tests for Kenyan debt collection workflow."""

from __future__ import annotations

import asyncio

from api.services.debt_collection.escalation import get_debt_escalation_rules
from api.services.debt_collection.installments import get_installment_scheduler
from api.services.debt_collection.negotiation import get_payment_negotiation_engine
from api.services.debt_collection.types import DebtAccount, DebtCollectionSession, EscalationRisk
from api.services.vertical_workflows.registry import get_vertical_workflow_registry


def test_debt_collection_template_registered():
    from api.services.debt_collection.engine import get_debt_collection_engine
    from api.services.debt_collection.template import KENYA_DEBT_COLLECTION

    registry = get_vertical_workflow_registry()
    get_debt_collection_engine()._ensure_template_registered()  # noqa: SLF001
    template = registry.get("kenya_debt_collection")
    assert template is not None
    assert template.template_id == KENYA_DEBT_COLLECTION.template_id
    assert template.industry.value == "debt_collection"
    assert template.integrations.mpesa is True


def test_negotiation_accepts_full_payment_offer():
    engine = get_payment_negotiation_engine()
    session = DebtCollectionSession(
        session_id="s1",
        organization_id=1,
        account=DebtAccount(
            account_id="A1",
            customer_name="Jane",
            phone_e164="+254712345678",
            outstanding_balance=10000.0,
        ),
    )
    offer = engine.evaluate_customer_offer(session, 10000.0)
    assert offer.acceptable is True
    assert session.outcome.value == "full_payment"


def test_negotiation_counter_on_low_offer():
    engine = get_payment_negotiation_engine()
    session = DebtCollectionSession(
        session_id="s2",
        organization_id=1,
        account=DebtAccount(
            account_id="A2",
            customer_name="John",
            phone_e164="+254700000001",
            outstanding_balance=10000.0,
        ),
    )
    offer = engine.evaluate_customer_offer(session, 200.0)
    assert offer.message_key == "counter_offer"
    assert offer.acceptable is False


def test_installment_scheduler_builds_plan():
    scheduler = get_installment_scheduler()
    account = DebtAccount(
        account_id="A3",
        customer_name="Mary",
        phone_e164="+254711111111",
        outstanding_balance=12000.0,
    )
    from api.services.debt_collection.types import NegotiationOffer

    offer = NegotiationOffer(
        offered_amount=12000.0,
        term_months=4,
        upfront_amount=3000.0,
        message_key="installment_offer",
    )
    plan = scheduler.build_plan(account, offer)
    assert len(plan.installments) >= 2
    assert plan.total_amount == 12000.0


def test_escalation_on_abusive_language():
    rules = get_debt_escalation_rules()
    session = DebtCollectionSession(session_id="s3", organization_id=1)
    decision = rules.assess(session, transcript="you are a stupid thief")
    assert decision.risk == EscalationRisk.CRITICAL
    assert decision.should_escalate is True


def test_debt_collection_engine_start():
    async def _run():
        from api.services.debt_collection.engine import get_debt_collection_engine

        engine = get_debt_collection_engine()
        return await engine.start(
            organization_id=1,
            account=DebtAccount(
                account_id="A4",
                customer_name="Peter",
                phone_e164="+254722222222",
                outstanding_balance=5000.0,
                days_past_due=30,
            ),
            locale="mixed",
        )

    data = asyncio.run(_run())
    assert data["session_id"]
    assert "prompt" in data
    assert data["negotiation_outcome"] == "pending"
