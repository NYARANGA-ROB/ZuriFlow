"""Unit tests for Kenyan conversational behavior layer."""

from __future__ import annotations

from api.services.kenyan_conversation.behavior import KenyanConversationBehavior
from api.services.kenyan_conversation.config import KenyanConversationConfig
from api.services.kenyan_conversation.middleware import ResponseStyleMiddleware
from api.services.kenyan_conversation.pacing import PacingController
from api.services.kenyan_conversation.interruption_recovery import InterruptionRecoveryPrompts
from api.services.kenyan_conversation.system_prompts import build_system_prompt
from api.services.kenyan_conversation.types import LanguageMode, TurnContext
from api.services.voice_pipeline.types import LLMMessage


def test_system_prompt_includes_kenyan_style():
    cfg = KenyanConversationConfig(enabled=True, language_mode=LanguageMode.MIXED)
    prompt = build_system_prompt(cfg)
    assert "Kenyan" in prompt
    assert "robotic" in prompt.lower()
    assert "Swahili" in prompt


def test_middleware_strips_robotic_opening():
    mw = ResponseStyleMiddleware(KenyanConversationConfig())
    mw.reset()
    out = ""
    for token in ["Certainly!", " Your ", "balance ", "is ", "500."]:
        out += mw.transform_token(token)
    final = mw.transform_complete(out)
    assert not final.lower().startswith("certainly")
    assert "balance" in final.lower()


def test_middleware_enforces_concise_sentences():
    cfg = KenyanConversationConfig(max_words_per_sentence=5, max_sentences_per_turn=2)
    mw = ResponseStyleMiddleware(cfg)
    long = "one two three four five six seven eight nine ten eleven twelve."
    result = mw.transform_complete(long)
    assert len(result.split()) <= 12


def test_pacing_splits_long_text():
    cfg = KenyanConversationConfig(max_tts_chunk_chars=40)
    pacing = PacingController(cfg)
    text = "Your balance is five thousand shillings, and your last payment was yesterday."
    chunks = pacing.chunks_for_tts(text)
    assert len(chunks) >= 2
    assert all(c.text for c in chunks)


def test_pacing_extra_pause_after_interrupt():
    cfg = KenyanConversationConfig(post_interrupt_pause_ms=300)
    pacing = PacingController(cfg)
    ctx = TurnContext(was_interrupted=True)
    assert pacing.pause_before_resume(ctx) == 300


def test_recovery_prompt_on_interrupt():
    recovery = InterruptionRecoveryPrompts(
        KenyanConversationConfig(language_mode=LanguageMode.MIXED)
    )
    ctx = TurnContext(was_interrupted=True, partial_spoken="Your balance is")
    prefix = recovery.recovery_prefix(ctx)
    assert prefix is not None
    assert len(prefix) > 0


def test_behavior_prepares_recovery_messages():
    behavior = KenyanConversationBehavior(
        KenyanConversationConfig(enabled=True, language_mode=LanguageMode.MIXED)
    )
    ctx = behavior.begin_turn(was_interrupted=True, partial_spoken="half answer")
    messages = [LLMMessage(role="user", content="wait")]
    updated = behavior.prepare_messages(messages, ctx)
    assert len(updated) >= 2


def test_multilingual_templates_mixed_confirmations():
    from api.services.kenyan_conversation.templates import confirmations

    mixed = confirmations(LanguageMode.MIXED)
    assert any("sawa" in c.lower() for c in mixed)


def test_transform_response_preserves_intent():
    behavior = KenyanConversationBehavior(KenyanConversationConfig())
    ctx = behavior.begin_turn()
    raw = "Certainly! Your account balance is 1,200 shillings."
    cleaned = behavior.transform_response(raw, ctx)
    assert "1,200" in cleaned or "balance" in cleaned.lower()
    assert "Certainly" not in cleaned
