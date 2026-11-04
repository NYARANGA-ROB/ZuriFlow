"""Kenyan conversational behavior layer — orchestrates prompts, style, pacing, recovery."""

from __future__ import annotations

from api.services.kenyan_conversation.config import (
    DEFAULT_KENYAN_CONVERSATION_CONFIG,
    KenyanConversationConfig,
)
from api.services.kenyan_conversation.interruption_recovery import InterruptionRecoveryPrompts
from api.services.kenyan_conversation.middleware import ResponseStyleMiddleware
from api.services.kenyan_conversation.pacing import PacingController
from api.services.kenyan_conversation.system_prompts import build_system_prompt, build_turn_hint
from api.services.kenyan_conversation.types import StyledChunk, TurnContext
from api.services.voice_pipeline.types import LLMMessage


class KenyanConversationBehavior:
    """Single entry point for Kenyan voice agent conversational behavior."""

    def __init__(self, config: KenyanConversationConfig = DEFAULT_KENYAN_CONVERSATION_CONFIG) -> None:
        self.config = config
        self.style = ResponseStyleMiddleware(config)
        self.pacing = PacingController(config)
        self.recovery = InterruptionRecoveryPrompts(config)
        self._turn_index = 0

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def system_prompt(self, *, custom_instructions: str = "") -> str:
        return build_system_prompt(self.config, custom_instructions=custom_instructions)

    def begin_turn(self, *, was_interrupted: bool = False, partial_spoken: str = "") -> TurnContext:
        self._turn_index += 1
        self.style.reset()
        return TurnContext(
            was_interrupted=was_interrupted,
            partial_spoken=partial_spoken,
            turn_index=self._turn_index,
        )

    def normalize_caller_text(self, text: str) -> str:
        if not self.config.normalize_caller_input:
            return text.strip()
        try:
            from api.services.kenyan_normalize.integration import normalize_transcript

            return normalize_transcript(text).normalized
        except Exception:
            return text.strip()

    def prepare_messages(
        self,
        messages: list[LLMMessage],
        ctx: TurnContext,
    ) -> list[LLMMessage]:
        if ctx.was_interrupted:
            raw = self.recovery.inject_recovery_message(messages, ctx)
            return [LLMMessage(role=m.role, content=m.content) for m in raw]
        return messages

    def transform_token(self, token: str) -> str:
        return self.style.transform_token(token)

    def transform_response(self, text: str, ctx: TurnContext | None = None) -> str:
        cleaned = self.style.transform_complete(text)
        if ctx and ctx.was_interrupted:
            prefix = self.recovery.spoken_recovery(ctx)
            if prefix and not cleaned.lower().startswith(prefix.lower()[:4]):
                pass  # recovery handled via message injection, not double-prefix
        return cleaned

    def tts_chunks(self, text: str, ctx: TurnContext) -> list[StyledChunk]:
        return self.pacing.chunks_for_tts(text, ctx=ctx)

    def turn_hint(self, caller_text: str) -> str | None:
        return build_turn_hint(self.config, caller_language_hint=caller_text)

    def pause_before_resume_ms(self, ctx: TurnContext) -> int:
        return self.pacing.pause_before_resume(ctx)
