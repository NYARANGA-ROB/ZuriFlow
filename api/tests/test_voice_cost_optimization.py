"""Tests for voice cost optimization."""

from __future__ import annotations

import pytest

from api.services.voice_cost_optimization.prerecorded import match_prerecorded, prerecorded_text
from api.services.voice_cost_optimization.routing_engine import IntelligentRoutingEngine
from api.services.voice_cost_optimization.types import ResponseSource, TurnComplexity


def test_prerecorded_greeting():
    matched = match_prerecorded("hello there", locale="en")
    assert matched is not None
    key, text = matched
    assert key == "greeting"
    assert "Hello" in text


def test_prerecorded_text_locales():
    assert prerecorded_text("goodbye", locale="sw") is not None


def test_routing_simple_acknowledgement():
    engine = IntelligentRoutingEngine()
    decision = engine.classify("yes", turn_count=1)
    assert decision.complexity == TurnComplexity.SIMPLE
    assert decision.skip_llm is True
    assert decision.max_output_tokens <= 128


def test_routing_complex_negotiation():
    engine = IntelligentRoutingEngine()
    decision = engine.classify(
        "I want to negotiate an installment payment plan for my debt",
        turn_count=3,
    )
    assert decision.complexity == TurnComplexity.COMPLEX


@pytest.mark.asyncio
async def test_hybrid_resolves_prerecorded():
    from api.services.voice_cost_optimization.hybrid_engine import HybridResponseEngine

    hybrid = HybridResponseEngine()
    resolution = await hybrid.resolve_turn(
        "hello",
        organization_id=1,
        locale="en",
    )
    assert resolution.source == ResponseSource.PRERECORDED
    assert resolution.text


@pytest.mark.asyncio
async def test_token_tracker_records_savings():
    from api.services.voice_cost_optimization.token_tracker import TokenTracker
    from api.services.voice_cost_optimization.types import HybridResolution, RoutingDecision

    tracker = TokenTracker()
    routing = IntelligentRoutingEngine().classify("hi")
    resolution = HybridResolution(
        source=ResponseSource.PRERECORDED,
        text="Hello",
        routing=routing,
    )
    tracker.record_hybrid_resolution("sess-1", resolution, user_text="hi")
    record = tracker.session("sess-1", organization_id=1)
    assert record.prerecorded_hits == 1
    assert record.tokens_saved > 0
