"""Tests for streaming LLM token handler, conversation memory, and cancellation."""

import pytest

from api.services.streaming_llm.cancellation import GenerationCancellationRegistry
from api.services.streaming_llm.config import StreamingLLMConfig
from api.services.streaming_llm.conversation import ConversationStateManager
from api.services.streaming_llm.tokens import TokenStreamingHandler
from api.services.streaming_llm.types import ResponseStreamKind


def test_token_handler_emits_sentence_partial():
    cfg = StreamingLLMConfig(min_sentence_chars=5)
    handler = TokenStreamingHandler("g1", cfg)
    events = handler.on_token_delta("Hello there. ")
    kinds = [e.kind for e in events]
    assert ResponseStreamKind.TOKEN_DELTA in kinds
    assert ResponseStreamKind.SENTENCE_PARTIAL in kinds
    partials = [e for e in events if e.kind == ResponseStreamKind.SENTENCE_PARTIAL]
    assert "Hello there." in partials[0].text


def test_token_handler_generation_end():
    handler = TokenStreamingHandler("g1")
    handler.on_token_delta("Complete response.")
    end_events = handler.on_generation_end()
    assert end_events[-1].kind == ResponseStreamKind.GENERATION_END
    assert end_events[-1].text == "Complete response."


def test_conversation_memory_trim():
    cfg = StreamingLLMConfig(max_messages=3)
    conv = ConversationStateManager(cfg)
    conv.append_user("one")
    conv.append_user("two")
    conv.append_user("three")
    conv.append_user("four")
    assert len(conv.messages()) == 3
    assert conv.messages()[0].content == "two"


def test_cancellation_registry():
    reg = GenerationCancellationRegistry()
    token = reg.create("gen-1")
    reg.set_response_id("gen-1", "resp-abc")
    assert reg.current_response_id() == "resp-abc"
    reg.cancel("gen-1")
    assert token.is_cancelled


def test_token_handler_reset_on_interrupt():
    handler = TokenStreamingHandler("g1")
    handler.on_token_delta("partial")
    events = handler.reset()
    assert events[0].kind == ResponseStreamKind.CANCELLED
    assert handler._buffer == ""
