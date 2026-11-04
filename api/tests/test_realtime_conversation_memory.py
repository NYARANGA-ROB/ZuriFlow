"""Unit tests for realtime conversation memory."""

from __future__ import annotations

import asyncio

import pytest

from api.services.realtime_conversation_memory.config import RealtimeMemoryConfig
from api.services.realtime_conversation_memory.intent import IntentTracker
from api.services.realtime_conversation_memory.retrieval import AsyncRetrievalService
from api.services.realtime_conversation_memory.service import RealtimeConversationMemoryService
from api.services.realtime_conversation_memory.state import ConversationStateManager
from api.services.realtime_conversation_memory.store import MemoryStore
from api.services.realtime_conversation_memory.summarizer import ContextSummarizer
from api.services.realtime_conversation_memory.types import CallIntent


@pytest.fixture
def memory_svc() -> RealtimeConversationMemoryService:
    return RealtimeConversationMemoryService(
        RealtimeMemoryConfig(enabled=True, pause_recovery_s=0.01, max_turns=8)
    )


def test_intent_tracker_balance():
    tracker = IntentTracker(RealtimeMemoryConfig())
    state = tracker.update("nataka balance yangu")
    assert state.current == CallIntent.REQUEST_BALANCE
    assert state.confidence > 0.5


def test_store_interruption(memory_svc: RealtimeConversationMemoryService):
    mgr = memory_svc.session("s1")
    mgr.on_user_turn("check my balance")
    mgr.on_interruption("Your balance is")
    snap = mgr.snapshot()
    assert snap.interrupted
    assert "balance" in snap.partial_assistant.lower()


def test_summarizer_includes_intent():
    summarizer = ContextSummarizer(RealtimeMemoryConfig())
    from api.services.realtime_conversation_memory.intent import IntentTracker
    from api.services.realtime_conversation_memory.types import TurnRecord, TurnStatus

    tracker = IntentTracker(RealtimeMemoryConfig())
    intent = tracker.update("I want my balance")
    turns = [
        TurnRecord(
            turn_id=1,
            user_text="I want my balance",
            assistant_text="",
            status=TurnStatus.COMPLETE,
            intent=CallIntent.REQUEST_BALANCE,
        )
    ]
    summary = summarizer.summarize(turns, intent)
    assert "balance" in summary.lower() or "request_balance" in summary


@pytest.mark.asyncio
async def test_async_retrieval_low_latency(memory_svc: RealtimeConversationMemoryService):
    mgr = memory_svc.session("s2")
    mgr.on_user_turn("hello")
    mgr.on_assistant_complete("Hi, how can I help?", interrupted=False)
    messages, result = await memory_svc.prepare_messages("s2", [])
    assert result.latency_ms < 50.0
    assert "hello" in result.context_block.lower() or result.summary


@pytest.mark.asyncio
async def test_pause_recovery(memory_svc: RealtimeConversationMemoryService):
    cfg = RealtimeMemoryConfig(enabled=True, pause_recovery_s=0.0)
    store = MemoryStore(cfg)
    summarizer = ContextSummarizer(cfg)
    tracker = IntentTracker(cfg)
    mgr = ConversationStateManager("s3", store, tracker, summarizer, cfg)
    retrieval = AsyncRetrievalService(cfg, store)
    retrieval.bind(mgr)
    mgr.on_user_turn("what is my balance")
    mgr.on_assistant_complete("Your balance is 500", interrupted=False)
    await asyncio.sleep(0.02)
    result = await retrieval.retrieve("s3")
    assert result.recovered_from_pause or result.summary


def test_end_session_cleanup(memory_svc: RealtimeConversationMemoryService):
    memory_svc.session("s4").on_user_turn("bye")
    snap = memory_svc.end_session("s4")
    assert snap is not None
    assert memory_svc.end_session("s4") is None
