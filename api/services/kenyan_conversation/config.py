"""Configuration for Kenyan conversational behavior."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.constants import (
    KENYAN_CONVERSATION_DOMAIN,
    KENYAN_CONVERSATION_ENABLED,
    KENYAN_CONVERSATION_LANGUAGE_MODE,
)
from api.services.kenyan_conversation.types import LanguageMode


def _default_language_mode() -> LanguageMode:
    try:
        return LanguageMode(KENYAN_CONVERSATION_LANGUAGE_MODE)
    except ValueError:
        return LanguageMode.MIXED


@dataclass(frozen=True)
class KenyanConversationConfig:
    enabled: bool = KENYAN_CONVERSATION_ENABLED
    language_mode: LanguageMode = field(default_factory=_default_language_mode)

    # Response style
    max_words_per_sentence: int = 18
    max_sentences_per_turn: int = 3
    allow_mixed_swahili: bool = True
    strip_robotic_phrases: bool = True

    # Pacing (voice)
    base_pause_ms: int = 120
    comma_pause_ms: int = 200
    sentence_pause_ms: int = 350
    max_tts_chunk_chars: int = 80
    post_interrupt_pause_ms: int = 280

    # Interruption tolerance
    prefer_short_replies: bool = True
    acknowledge_interrupts: bool = True
    resume_after_interrupt: bool = True

    # Normalization
    normalize_caller_input: bool = True

    # Domain overlay (banking, support, general)
    domain: str = KENYAN_CONVERSATION_DOMAIN


DEFAULT_KENYAN_CONVERSATION_CONFIG = KenyanConversationConfig()
