"""Tests for intelligent call routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.call_routing.config import CallRoutingOrgConfig
from api.services.call_routing.fallback import CallRoutingFallbackHandler
from api.services.call_routing.i18n import escalation_ack, voice_prompt_for_destination
from api.services.call_routing.routing_engine import CallRoutingEngine
from api.services.call_routing.types import (
    CallRoutingPlan,
    FallbackStrategy,
    QueueEntry,
    RoutingDestination,
    RoutingStatus,
)
from api.services.kenyan_intent.classifier import KenyanIntentClassifier
from api.services.kenyan_intent.config import KenyanIntentConfig
from api.services.kenyan_intent.router import IntentRoutingEngine
from api.services.kenyan_intent.types import BusinessIntent, RouteAction


@pytest.fixture
def org_config() -> CallRoutingOrgConfig:
    return CallRoutingOrgConfig.from_dict(
        {
            "enabled": True,
            "language_queues": {
                "en": {"human": "human_en", "support": "support_en"},
                "sw": {"human": "human_sw", "support": "support_sw"},
            },
            "escalation": {
                "transfer_destination": "+254700000001",
                "notify_numbers": ["+254711111111"],
            },
        }
    )


def test_routing_engine_escalation_multilingual(org_config: CallRoutingOrgConfig):
    engine = CallRoutingEngine()
    route = IntentRoutingEngine().route(
        KenyanIntentClassifier(KenyanIntentConfig(use_normalization=False)).classify(
            "Nataka mtu wa customer care"
        ),
        confidence_threshold=0.55,
    )
    plan_en = engine.plan(route, org_config=org_config, language="en")
    plan_sw = engine.plan(route, org_config=org_config, language="sw")

    assert plan_en is not None
    assert plan_en.destination == RoutingDestination.HUMAN_QUEUE
    assert plan_en.queue_name == "human_en"
    assert plan_sw is not None
    assert plan_sw.queue_name == "human_sw"
    assert plan_en.voice_prompt


def test_routing_engine_support_queue(org_config: CallRoutingOrgConfig):
    engine = CallRoutingEngine()
    clf = KenyanIntentClassifier(KenyanIntentConfig(use_normalization=False))
    route = IntentRoutingEngine().route(
        clf.classify("I need help with my account"),
        confidence_threshold=0.55,
    )
    plan = engine.plan(route, org_config=org_config, language="en")
    assert plan is not None
    assert plan.destination == RoutingDestination.SUPPORT_QUEUE
    assert plan.queue_name == "support_en"


def test_routing_engine_payment_no_queue(org_config: CallRoutingOrgConfig):
    engine = CallRoutingEngine()
    clf = KenyanIntentClassifier(KenyanIntentConfig(use_normalization=False))
    route = IntentRoutingEngine().route(
        clf.classify("I want to pay via mpesa"),
        confidence_threshold=0.55,
    )
    plan = engine.plan(route, org_config=org_config, language="en")
    assert plan is not None
    assert plan.destination == RoutingDestination.PAYMENT_FLOW
    assert plan.queue_name == ""


def test_fallback_queue_full(org_config: CallRoutingOrgConfig):
    handler = CallRoutingFallbackHandler()
    plan = CallRoutingPlan(
        destination=RoutingDestination.HUMAN_QUEUE,
        queue_name="human_en",
        priority=100,
        reason="escalation",
        intent="escalation",
        confidence=0.9,
        language="en",
    )
    result = handler.handle_queue_full(plan, org_config=org_config)
    assert result.status == RoutingStatus.FALLBACK
    assert result.fallback_strategy == FallbackStrategy.CONTINUE_AI
    assert result.voice_prompt


def test_fallback_low_confidence(org_config: CallRoutingOrgConfig):
    handler = CallRoutingFallbackHandler()
    result = handler.handle_low_confidence(
        None,
        org_config=org_config,
        confidence=0.2,
    )
    assert result.status == RoutingStatus.FALLBACK


def test_fallback_queue_timeout_offers_callback(org_config: CallRoutingOrgConfig):
    handler = CallRoutingFallbackHandler()
    plan = CallRoutingPlan(
        destination=RoutingDestination.SUPPORT_QUEUE,
        queue_name="support_en",
        priority=60,
        reason="support",
        intent="support",
        confidence=0.8,
        language="sw",
    )
    result = handler.handle_queue_timeout(plan, org_config=org_config)
    assert result.fallback_strategy == FallbackStrategy.OFFER_CALLBACK
    assert "simu" in result.voice_prompt.lower() or "call" in result.voice_prompt.lower()


def test_i18n_escalation_ack():
    assert "patience" in escalation_ack("en").lower()
    assert "asante" in escalation_ack("sw").lower()
    assert "/" in escalation_ack("mixed")


@pytest.mark.asyncio
async def test_queue_service_enqueue():
    from api.services.call_routing.queue_service import CallRoutingQueueService

    fake = AsyncMock()
    fake.zcard = AsyncMock(return_value=0)
    fake.pipeline = MagicMock(return_value=fake)
    fake.zadd = AsyncMock()
    fake.expire = AsyncMock()
    fake.setex = AsyncMock()
    fake.execute = AsyncMock()
    fake.zrevrank = AsyncMock(return_value=0)

    svc = CallRoutingQueueService(redis_client=fake, ttl_s=60)
    org = CallRoutingOrgConfig.from_dict({"enabled": True})
    entry = QueueEntry(
        session_id="sess-1",
        organization_id=1,
        queue_name="human_en",
        priority=100,
        intent="escalation",
        language="en",
        enqueued_at=1.0,
    )
    ok, position = await svc.enqueue(entry, org_config=org)
    assert ok is True
    assert position == 1


@pytest.mark.asyncio
async def test_orchestrator_route_escalation(monkeypatch, org_config: CallRoutingOrgConfig):
    from api.services.call_routing.orchestrator import CallRoutingOrchestrator
    from api.services.call_routing.types import CallRoutingContext
    from api.services.kenyan_intent.types import RouteDecision

    fake_queue = AsyncMock()
    fake_queue.enqueue = AsyncMock(return_value=(True, 1))
    fake_escalation = AsyncMock()
    fake_escalation.escalate = AsyncMock(
        return_value={
            "escalated": True,
            "voice_prompt": "Please hold.",
            "pending_transfer": True,
        }
    )

    orch = CallRoutingOrchestrator(
        queue_service=fake_queue,
        escalation_manager=fake_escalation,
    )
    monkeypatch.setattr(orch, "load_org_config", AsyncMock(return_value=org_config))

    route = RouteDecision(
        action=RouteAction.TRIGGER_ESCALATION,
        intent=BusinessIntent.ESCALATION,
        confidence=0.95,
        priority=100,
        reason="Caller requested a human agent",
    )
    result = await orch.route_from_intent(
        route,
        CallRoutingContext(
            session_id="sess-1",
            organization_id=1,
            phone_e164="+254712345678",
        ),
        org_config=org_config,
    )
    assert result.status == RoutingStatus.ESCALATING
    assert result.escalated is True
    assert result.queue_position == 1
    fake_escalation.escalate.assert_awaited_once()
