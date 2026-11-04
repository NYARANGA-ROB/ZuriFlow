"""Interruption recovery prompts for natural conversation resume."""

from __future__ import annotations

import random

from api.services.kenyan_conversation.config import KenyanConversationConfig
from api.services.kenyan_conversation.templates import acknowledgments
from api.services.kenyan_conversation.types import LanguageMode, TurnContext

_RECOVERY_EN = [
    "Sorry — go ahead.",
    "Got it, I'm listening.",
    "No worries, please continue.",
]

_RECOVERY_SW = [
    "Samahani, endelea.",
    "Sawa, naskiza.",
    "Pole, sema tu.",
]

_RECOVERY_MIXED = [
    "Sawa, go ahead.",
    "Sorry — endelea.",
    "Poa, I'm listening.",
    "Sawa boss, carry on.",
]

_RESUME_EN = [
    "So, picking up —",
    "Right,",
    "Okay,",
]

_RESUME_SW = [
    "Sawa,",
    "Basically,",
]

_RESUME_MIXED = [
    "Sawa, so —",
    "Alright,",
    "Poa —",
]


class InterruptionRecoveryPrompts:
    """Generate culturally natural recovery lines after barge-in."""

    def __init__(self, config: KenyanConversationConfig) -> None:
        self._config = config

    def recovery_prefix(self, ctx: TurnContext) -> str | None:
        if not self._config.acknowledge_interrupts or not ctx.was_interrupted:
            return None

        pool = self._recovery_pool()
        prefix = random.choice(pool)

        if self._config.resume_after_interrupt and ctx.partial_spoken.strip():
            resume = random.choice(self._resume_pool())
            return f"{prefix} {resume}"

        return prefix

    def inject_recovery_message(
        self,
        messages: list,
        ctx: TurnContext,
    ) -> list:
        """Prepend a brief assistant recovery line to conversation context."""
        prefix = self.recovery_prefix(ctx)
        if not prefix:
            return messages

        from api.services.voice_pipeline.types import LLMMessage

        hint = LLMMessage(
            role="assistant",
            content=f"{prefix} (interrupted — listen to caller, then answer briefly)",
        )
        return [*messages, hint]

    def spoken_recovery(self, ctx: TurnContext) -> str | None:
        """Short line the agent can speak immediately after interrupt."""
        if not ctx.was_interrupted or not self._config.acknowledge_interrupts:
            return None
        ack = random.choice(acknowledgments(self._config.language_mode))
        return ack

    def _recovery_pool(self) -> list[str]:
        return {
            LanguageMode.ENGLISH: _RECOVERY_EN,
            LanguageMode.SWAHILI: _RECOVERY_SW,
            LanguageMode.MIXED: _RECOVERY_MIXED,
        }[self._config.language_mode]

    def _resume_pool(self) -> list[str]:
        return {
            LanguageMode.ENGLISH: _RESUME_EN,
            LanguageMode.SWAHILI: _RESUME_SW,
            LanguageMode.MIXED: _RESUME_MIXED,
        }[self._config.language_mode]
