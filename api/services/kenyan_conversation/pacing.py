"""Voice pacing controller for natural Kenyan phone rhythm."""

from __future__ import annotations

import re

from api.services.kenyan_conversation.config import KenyanConversationConfig
from api.services.kenyan_conversation.types import StyledChunk, TurnContext


class PacingController:
    """Split TTS output and insert natural pauses between phrases."""

    def __init__(self, config: KenyanConversationConfig) -> None:
        self._config = config

    def chunks_for_tts(self, text: str, *, ctx: TurnContext | None = None) -> list[StyledChunk]:
        if not text.strip():
            return []

        segments = self._split_segments(text)
        result: list[StyledChunk] = []
        post_interrupt = ctx.was_interrupted if ctx else False

        for i, segment in enumerate(segments):
            pause = self._pause_after(segment, is_last=(i == len(segments) - 1))
            if post_interrupt and i == 0:
                pause = max(pause, self._config.post_interrupt_pause_ms)
            result.append(StyledChunk(text=segment, pause_after_ms=pause))

        return result

    def pause_before_resume(self, ctx: TurnContext) -> int:
        """Extra pause after caller interrupts — gives room to speak."""
        if not ctx.was_interrupted:
            return 0
        return self._config.post_interrupt_pause_ms

    def _split_segments(self, text: str) -> list[str]:
        max_chars = self._config.max_tts_chunk_chars
        raw_parts = re.split(r"([,;])", text)
        merged: list[str] = []
        current = ""
        for part in raw_parts:
            if part in {",", ";"}:
                current += part
                continue
            candidate = (current + part).strip()
            if len(candidate) <= max_chars:
                current = candidate + " " if candidate else ""
            else:
                if current.strip():
                    merged.append(current.strip())
                current = part.strip() + " " if part.strip() else ""
        if current.strip():
            merged.append(current.strip())

        if not merged:
            return [text.strip()]
        return merged

    def _pause_after(self, segment: str, *, is_last: bool) -> int:
        if is_last:
            return self._config.base_pause_ms
        if segment.rstrip().endswith(","):
            return self._config.comma_pause_ms
        if segment.rstrip().endswith((".", "!", "?")):
            return self._config.sentence_pause_ms
        return self._config.base_pause_ms
