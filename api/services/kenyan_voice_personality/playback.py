"""Interruption-aware playback adaptation layer."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from api.services.kenyan_conversation.config import KenyanConversationConfig
from api.services.kenyan_conversation.pacing import PacingController
from api.services.kenyan_conversation.types import StyledChunk, TurnContext
from api.services.kenyan_voice_personality.schema import ResolvedVoicePersonality


@dataclass
class PlaybackPlan:
    """Adapted TTS playback plan for one agent turn."""

    chunks: list[StyledChunk] = field(default_factory=list)
    pause_before_ms: int = 0
    speed_multiplier: float = 1.0
    truncate_on_interrupt: bool = True
    barge_in_enabled: bool = True
    generation_id: str = ""


class PlaybackAdaptationLayer:
    """Adapt chunking, pauses, and interruption behavior per voice profile."""

    def __init__(self, resolved: ResolvedVoicePersonality) -> None:
        self._resolved = resolved
        self._settings = resolved.profile.playback
        self._pacing = PacingController(self._conversation_config())

    def _conversation_config(self) -> KenyanConversationConfig:
        pb = self._resolved.profile.playback
        return replace(
            KenyanConversationConfig(),
            post_interrupt_pause_ms=pb.post_interrupt_pause_ms,
            max_tts_chunk_chars=pb.max_tts_chunk_chars,
            base_pause_ms=pb.base_pause_ms,
            comma_pause_ms=pb.comma_pause_ms,
            sentence_pause_ms=pb.sentence_pause_ms,
            acknowledge_interrupts=pb.acknowledge_interrupt,
        )

    def plan_turn(
        self,
        text: str,
        *,
        ctx: TurnContext | None = None,
        generation_id: str = "",
    ) -> PlaybackPlan:
        ctx = ctx or TurnContext()
        chunks = self._pacing.chunks_for_tts(text, ctx=ctx)

        if ctx.was_interrupted and self._settings.truncate_on_interrupt:
            chunks = self._apply_interrupt_truncation(chunks)

        pause_before = 0
        if ctx.was_interrupted:
            pause_before = max(
                self._pacing.pause_before_resume(ctx),
                self._settings.resume_soft_start_ms,
            )

        return PlaybackPlan(
            chunks=chunks,
            pause_before_ms=pause_before,
            speed_multiplier=self._resolved.effective_speed,
            truncate_on_interrupt=self._settings.truncate_on_interrupt,
            barge_in_enabled=self._settings.barge_in_enabled,
            generation_id=generation_id,
        )

    def on_interrupt(self, plan: PlaybackPlan, *, partial_spoken: str = "") -> PlaybackPlan:
        if not plan.truncate_on_interrupt:
            return plan
        kept: list[StyledChunk] = []
        if partial_spoken.strip():
            kept.append(
                StyledChunk(
                    text=partial_spoken.strip(),
                    pause_after_ms=self._settings.post_interrupt_pause_ms,
                )
            )
        return PlaybackPlan(
            chunks=kept,
            pause_before_ms=self._settings.post_interrupt_pause_ms,
            speed_multiplier=plan.speed_multiplier * 0.95,
            truncate_on_interrupt=True,
            barge_in_enabled=plan.barge_in_enabled,
            generation_id=plan.generation_id,
        )

    @staticmethod
    def _apply_interrupt_truncation(chunks: list[StyledChunk]) -> list[StyledChunk]:
        if not chunks:
            return chunks
        first = chunks[0]
        words = first.text.split()
        if len(words) > 8:
            first = StyledChunk(
                text=" ".join(words[:8]) + "...",
                pause_after_ms=first.pause_after_ms,
            )
        return [first]
