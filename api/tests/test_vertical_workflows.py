"""Tests for vertical workflow architecture."""

from __future__ import annotations

import asyncio

from api.services.vertical_workflows.engine import get_vertical_workflow_engine
from api.services.vertical_workflows.registry import get_vertical_workflow_registry
from api.services.vertical_workflows.rules import (
    evaluate_condition,
    get_business_rule_engine,
)
from api.services.vertical_workflows.schema import (
    BusinessRule,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleOperator,
    WorkflowEvent,
    WorkflowEventType,
)


def test_registry_lists_builtin_templates():
    registry = get_vertical_workflow_registry()
    templates = registry.list_templates()
    ids = {t.template_id for t in templates}
    assert "kenya_fintech_support" in ids
    assert "general_customer_support" in ids
    assert "kenya_mp_sacco" in ids
    assert "kenya_mp_contact_center" in ids


def test_rule_engine_matches_intent():
    engine = get_business_rule_engine()
    rule = BusinessRule(
        rule_id="pay",
        name="payment",
        when=RuleCondition("intent", RuleOperator.INTENT_IS, "payment"),
        then=(RuleAction(RuleActionType.REQUEST_PAYMENT, {}),),
        priority=1,
    )
    actions = engine.evaluate((rule,), {"intent": "payment"})
    assert len(actions) == 1
    assert actions[0].action == RuleActionType.REQUEST_PAYMENT


def test_evaluate_condition_language_in():
    cond = RuleCondition("language", RuleOperator.LANGUAGE_IN, ["en", "sw"])
    assert evaluate_condition(cond, {"language": "sw"})
    assert not evaluate_condition(cond, {"language": "fr"})


def test_engine_starts_fintech_template():
    async def _run():
        engine = get_vertical_workflow_engine()
        return await engine.start(
            template_id="kenya_fintech_support",
            organization_id=1,
            locale="mixed",
            initial_variables={"phone_e164": "+254712345678"},
        )

    result = asyncio.run(_run())
    assert result.current_step_id == "greeting"
    assert result.status.value == "running"
    assert "fintech" in result.prompt.lower() or "support" in result.prompt.lower()


def test_engine_processes_payment_intent():
    async def _run():
        engine = get_vertical_workflow_engine()
        started = await engine.start(
            template_id="kenya_fintech_support",
            organization_id=1,
        )
        await engine.process_event(
            started.instance_id,
            WorkflowEvent(WorkflowEventType.MANUAL, {"step_id": "support"}),
        )
        return await engine.process_event(
            started.instance_id,
            WorkflowEvent(
                WorkflowEventType.INTENT,
                {"intent": {"name": "payment", "confidence": 0.9}},
            ),
        )

    result = asyncio.run(_run())
    assert result.payment_requested or result.current_step_id == "collect_payment"
