"""Token streaming and partial sentence emission."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.services.streaming_llm.config import StreamingLLMConfig, DEFAULT_STREAMING_LLM_CONFIG
from api.services.streaming_llm.types import ResponseStreamEvent, ResponseStreamKind


@dataclass
class TokenStreamingHandler:
    """Accumulates token deltas and emits sentence-sized partials for TTS."""

    generation_id: str
    config: StreamingLLMConfig = DEFAULT_STREAMING_LLM_CONFIG
    _buffer: str = ""
    _committed: str = ""
    _sentence_carry: str = ""

    def reset(self, *, generation_id: str | None = None) -> list[ResponseStreamEvent]:
        events: list[ResponseStreamEvent] = []
        if self._buffer or self._sentence_carry:
            events.append(
                ResponseStreamEvent(
                    kind=ResponseStreamKind.CANCELLED,
                    generation_id=generation_id or self.generation_id,
                    text=self._buffer,
                )
            )
        self._buffer = ""
        self._committed = ""
        self._sentence_carry = ""
        if generation_id:
            self.generation_id = generation_id
        return events

    def on_token_delta(self, delta: str) -> list[ResponseStreamEvent]:
        if not delta:
            return []
        self._buffer += delta
        events = [
            ResponseStreamEvent(
                kind=ResponseStreamKind.TOKEN_DELTA,
                generation_id=self.generation_id,
                text=self._buffer,
                delta=delta,
            )
        ]
        if self.config.emit_partial_on_delimiter:
            events.extend(self._extract_sentence_partials())
        return events

    def on_generation_end(self, final_text: str | None = None) -> list[ResponseStreamEvent]:
        text = (final_text or self._buffer).strip()
        events: list[ResponseStreamEvent] = []
        remainder = self._sentence_carry.strip()
        if remainder:
            events.append(
                ResponseStreamEvent(
                    kind=ResponseStreamKind.SENTENCE_PARTIAL,
                    generation_id=self.generation_id,
                    text=remainder,
                    delta=remainder,
                    is_final=False,
                )
            )
        if text:
            events.append(
                ResponseStreamEvent(
                    kind=ResponseStreamKind.GENERATION_END,
                    generation_id=self.generation_id,
                    text=text,
                    is_final=True,
                )
            )
        self._committed = text
        self._buffer = ""
        self._sentence_carry = ""
        return events

    def _extract_sentence_partials(self) -> list[ResponseStreamEvent]:
        events: list[ResponseStreamEvent] = []
        carry = self._sentence_carry + self._buffer[len(self._committed) :]
        if not carry:
            return events

        start = 0
        for idx, ch in enumerate(carry):
            if ch not in self.config.sentence_delimiters:
                continue
            segment = carry[start : idx + 1].strip()
            if len(segment) >= self.config.min_sentence_chars:
                events.append(
                    ResponseStreamEvent(
                        kind=ResponseStreamKind.SENTENCE_PARTIAL,
                        generation_id=self.generation_id,
                        text=segment,
                        delta=segment,
                    )
                )
                start = idx + 1

        self._sentence_carry = carry[start:]
        self._committed = self._buffer
        return events
