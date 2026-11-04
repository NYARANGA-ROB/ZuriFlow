"""Tests for automated post-call WhatsApp workflow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.whatsapp.config import WhatsAppOrgConfig
from api.services.whatsapp.post_call.config import PostCallWorkflowConfig
from api.services.whatsapp.post_call.escalation import PostCallEscalationEvaluator
from api.services.whatsapp.post_call.orchestrator import PostCallWhatsAppOrchestrator
from api.services.whatsapp.post_call.summary import (
    PostCallSummaryGenerator,
    extract_customer_phone,
)
from api.services.whatsapp.post_call.types import FollowUpAction, PostCallSummary
from api.services.whatsapp.templates.i18n import detect_language


def test_detect_language_swahili():
    assert detect_language("nataka salio yangu na saidia tafadhali", "en") == "sw"


def test_extract_customer_phone_outbound():
    run = SimpleNamespace(
        initial_context={"direction": "outbound", "to_number": "+254712345678"},
        gathered_context={},
    )
    assert extract_customer_phone(run) == "+254712345678"


def test_summary_from_memory_snapshot():
    generator = PostCallSummaryGenerator()
    run = SimpleNamespace(
        gathered_context={
            "conversation_memory": {
                "summary": "Caller asked about payment.",
                "intent": {"current": "request_payment", "confidence": 0.9, "slots": {"amount": "500"}},
            }
        },
        initial_context={},
        logs={},
    )
    summary = generator.generate(workflow_run=run, config=PostCallWorkflowConfig())
    assert "payment" in summary.text.lower() or "Caller" in summary.text
    assert summary.intent == "request_payment"
    assert summary.slots.get("amount") == "500"


def test_escalation_evaluator_support_intent():
    evaluator = PostCallEscalationEvaluator()
    summary = PostCallSummary(
        text="Need help",
        intent="request_support",
        intent_confidence=0.8,
        next_steps="",
        language="en",
    )
    should, reason = evaluator.should_escalate(
        summary=summary,
        gathered_context={},
        config=PostCallWorkflowConfig(),
    )
    assert should is True
    assert "request_support" in reason


@pytest.mark.asyncio
async def test_orchestrator_skips_when_disabled():
    orchestrator = PostCallWhatsAppOrchestrator()
    org_config = WhatsAppOrgConfig(
        enabled=True,
        default_provider="meta",
        post_call=PostCallWorkflowConfig(enabled=False),
    )
    run = SimpleNamespace(
        id=42,
        gathered_context={},
        initial_context={"to_number": "+254700000001"},
        logs={},
    )

    with (
        patch(
            "api.services.whatsapp.post_call.orchestrator.db_client.get_workflow_run_by_id",
            AsyncMock(return_value=run),
        ),
        patch(
            "api.services.whatsapp.post_call.orchestrator.db_client.get_organization_id_by_workflow_run_id",
            AsyncMock(return_value=1),
        ),
        patch.object(orchestrator, "_load_org_config", AsyncMock(return_value=org_config)),
    ):
        result = await orchestrator.run(42)

    assert result.skipped is True
    assert result.skip_reason == "whatsapp_post_call_disabled"


@pytest.mark.asyncio
async def test_orchestrator_runs_summary_and_payment():
    orchestrator = PostCallWhatsAppOrchestrator()
    org_config = WhatsAppOrgConfig(
        enabled=True,
        default_provider="meta",
        meta=MagicMock(access_token="t", phone_number_id="p"),
        post_call=PostCallWorkflowConfig(
            enabled=True,
            auto_send_summary=True,
            auto_send_payment_link=True,
            auto_escalate=False,
        ),
    )
    run = SimpleNamespace(
        id=99,
        gathered_context={
            "conversation_memory": {
                "summary": "Payment discussed.",
                "intent": {"current": "request_payment", "confidence": 0.95, "slots": {}},
            },
            "payment_url": "https://pay.test/abc",
        },
        initial_context={"to_number": "+254700000002", "customer_name": "Jane"},
        logs={},
    )

    mock_summary_step = MagicMock(success=True, detail={"success": True})
    mock_payment_step = MagicMock(success=True, detail={"success": True})

    with (
        patch(
            "api.services.whatsapp.post_call.orchestrator.db_client.get_workflow_run_by_id",
            AsyncMock(return_value=run),
        ),
        patch(
            "api.services.whatsapp.post_call.orchestrator.db_client.get_organization_id_by_workflow_run_id",
            AsyncMock(return_value=1),
        ),
        patch.object(orchestrator, "_load_org_config", AsyncMock(return_value=org_config)),
        patch.object(
            orchestrator._store,
            "get_or_create",
            AsyncMock(return_value=SimpleNamespace(id=7)),
        ),
        patch.object(
            orchestrator._dispatcher,
            "send_summary",
            AsyncMock(return_value=mock_summary_step),
        ),
        patch.object(
            orchestrator._dispatcher,
            "send_payment_link",
            AsyncMock(return_value=mock_payment_step),
        ),
        patch.object(orchestrator._recovery, "persist_workflow_state", AsyncMock()),
        patch.object(orchestrator, "_persist_run_outcome", AsyncMock()),
    ):
        result = await orchestrator.run(99)

    assert result.skipped is False
    assert result.follow_up_action == FollowUpAction.PAYMENT
    assert len(result.steps) >= 3
