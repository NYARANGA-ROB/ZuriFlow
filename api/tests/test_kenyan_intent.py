"""Tests for Kenyan realtime business intent detection."""

from __future__ import annotations

import pytest

from api.services.kenyan_intent.classifier import KenyanIntentClassifier
from api.services.kenyan_intent.config import KenyanIntentConfig
from api.services.kenyan_intent.integration import (
    system_hint_from_route,
    voice_mpesa_intent_from_route,
)
from api.services.kenyan_intent.router import IntentRoutingEngine
from api.services.kenyan_intent.service import RealtimeIntentInferenceService
from api.services.kenyan_intent.types import BusinessIntent, RouteAction, TranscriptKind


@pytest.fixture
def classifier() -> KenyanIntentClassifier:
    return KenyanIntentClassifier(KenyanIntentConfig(use_normalization=False))


@pytest.fixture
def service() -> RealtimeIntentInferenceService:
    return RealtimeIntentInferenceService(
        KenyanIntentConfig(enabled=True, use_normalization=False)
    )


def test_payment_intent_english(classifier: KenyanIntentClassifier):
    result = classifier.classify("I want to pay via M-Pesa")
    assert result.intent == BusinessIntent.PAYMENT
    assert result.confidence >= 0.6
    assert "mpesa" in result.matched_phrases or "pay" in result.matched_phrases


def test_payment_intent_swahili(classifier: KenyanIntentClassifier):
    result = classifier.classify("Nataka kulipa kwa M-Pesa")
    assert result.intent == BusinessIntent.PAYMENT
    assert result.confidence >= 0.6
    assert result.language in {"sw", "mixed"}


def test_booking_intent(classifier: KenyanIntentClassifier):
    result = classifier.classify("Nataka miadi ya kesho")
    assert result.intent == BusinessIntent.BOOKING
    assert result.confidence >= 0.6


def test_escalation_intent(classifier: KenyanIntentClassifier):
    result = classifier.classify("I need to speak to someone please")
    assert result.intent == BusinessIntent.ESCALATION
    assert result.confidence >= 0.6


def test_support_intent(classifier: KenyanIntentClassifier):
    result = classifier.classify("Nina shida na account yangu, saidia")
    assert result.intent == BusinessIntent.SUPPORT
    assert result.confidence >= 0.5


def test_callback_intent(classifier: KenyanIntentClassifier):
    result = classifier.classify("Please call me back later")
    assert result.intent == BusinessIntent.CALLBACK
    assert result.confidence >= 0.6


def test_slot_extraction_amount_and_phone(classifier: KenyanIntentClassifier):
    result = classifier.classify("Lipa 500 KES kwa simu 0712345678")
    assert result.intent == BusinessIntent.PAYMENT
    assert "amount" in result.slots
    assert "phone" in result.slots


def test_router_payment_action(classifier: KenyanIntentClassifier):
    result = classifier.classify("Send money via mpesa")
    router = IntentRoutingEngine()
    route = router.route(result, confidence_threshold=0.55)
    assert route.action == RouteAction.TRIGGER_MPESA_PAYMENT
    assert route.intent == BusinessIntent.PAYMENT


def test_router_low_confidence_continues(classifier: KenyanIntentClassifier):
    result = classifier.classify("maybe")
    router = IntentRoutingEngine()
    route = router.route(result, confidence_threshold=0.6)
    assert route.action == RouteAction.CONTINUE


def test_voice_mpesa_intent_mapping(classifier: KenyanIntentClassifier):
    result = classifier.classify("I want to pay now")
    router = IntentRoutingEngine()
    route = router.route(result, confidence_threshold=0.55)
    assert voice_mpesa_intent_from_route(route) == "request_payment"


def test_system_hint_from_route(classifier: KenyanIntentClassifier):
    result = classifier.classify("Transfer me to a human agent")
    router = IntentRoutingEngine()
    route = router.route(result, confidence_threshold=0.55)
    hint = system_hint_from_route(route)
    assert hint is not None
    assert "escalation" in hint


@pytest.mark.asyncio
async def test_realtime_service_final_commit(service: RealtimeIntentInferenceService):
    result, route = await service.infer("sess-1", "Book an appointment for tomorrow", kind=TranscriptKind.FINAL)
    assert result.intent == BusinessIntent.BOOKING
    assert route.action == RouteAction.TRIGGER_BOOKING
    snap = service.get_session_snapshot("sess-1")
    assert snap["current_intent"] == "booking"


@pytest.mark.asyncio
async def test_interruption_safe_processing(service: RealtimeIntentInferenceService):
    await service.infer("sess-2", "I want to pay via mpesa", kind=TranscriptKind.FINAL)
    service.on_interrupt("sess-2", partial_text="wait let me")
    snap = service.get_session_snapshot("sess-2")
    assert snap["interrupted"] is True
    assert snap["current_intent"] == "interruption"

    service.on_resume("sess-2")
    snap = service.get_session_snapshot("sess-2")
    assert snap["interrupted"] is False
    assert snap["current_intent"] == "payment"


@pytest.mark.asyncio
async def test_partial_inference_low_commit_threshold(service: RealtimeIntentInferenceService):
    cfg = KenyanIntentConfig(
        enabled=True,
        use_normalization=False,
        commit_on_partial=False,
        partial_confidence_threshold=0.99,
    )
    svc = RealtimeIntentInferenceService(cfg)
    result, _route = await svc.infer("sess-3", "nataka kulipa", kind=TranscriptKind.PARTIAL)
    assert result.is_partial is True
    snap = svc.get_session_snapshot("sess-3")
    assert snap.get("current_intent", "unknown") in {"unknown", "payment"}


def test_latency_under_budget(classifier: KenyanIntentClassifier):
    result = classifier.classify("Nataka mtu wa customer care")
    assert result.latency_ms < 50.0
