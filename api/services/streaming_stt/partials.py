"""Partial and incremental transcript aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.services.streaming_stt.types import (
    StreamingTranscriptEvent,
    StreamingTranscriptKind,
)


@dataclass
class PartialTranscriptHandler:
    """Normalizes provider partials into stable partial/incremental/final events."""

    provider: str = ""
    _committed: str = ""
    _latest_partial: str = ""
    _speech_active: bool = False

    def reset(self, *, interrupted: bool = False) -> StreamingTranscriptEvent | None:
        self._committed = ""
        self._latest_partial = ""
        was_active = self._speech_active
        self._speech_active = False
        if interrupted and was_active:
            return StreamingTranscriptEvent(
                text="",
                kind=StreamingTranscriptKind.INTERRUPTED,
                provider=self.provider,
            )
        return None

    def on_speech_start(self) -> StreamingTranscriptEvent:
        self._speech_active = True
        return StreamingTranscriptEvent(
            text="",
            kind=StreamingTranscriptKind.SPEECH_START,
            provider=self.provider,
        )

    def on_speech_end(self) -> StreamingTranscriptEvent:
        self._speech_active = False
        return StreamingTranscriptEvent(
            text="",
            kind=StreamingTranscriptKind.SPEECH_END,
            provider=self.provider,
        )

    def on_partial(
        self,
        text: str,
        *,
        confidence: float | None = None,
        language: str | None = None,
        start_ms: float | None = None,
        end_ms: float | None = None,
    ) -> list[StreamingTranscriptEvent]:
        if not text:
            return []
        events: list[StreamingTranscriptEvent] = []
        if not self._speech_active:
            events.append(self.on_speech_start())

        delta = _suffix_delta(self._latest_partial, text)
        self._latest_partial = text

        events.append(
            StreamingTranscriptEvent(
                text=text,
                kind=StreamingTranscriptKind.PARTIAL,
                is_final=False,
                confidence=confidence,
                language=language,
                provider=self.provider,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )
        if delta:
            events.append(
                StreamingTranscriptEvent(
                    text=text,
                    kind=StreamingTranscriptKind.INCREMENTAL,
                    is_final=False,
                    delta=delta,
                    confidence=confidence,
                    language=language,
                    provider=self.provider,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            )
        return events

    def on_final(
        self,
        text: str,
        *,
        confidence: float | None = None,
        language: str | None = None,
        start_ms: float | None = None,
        end_ms: float | None = None,
    ) -> list[StreamingTranscriptEvent]:
        if not text.strip():
            return []
        self._committed = _join_text(self._committed, text)
        self._latest_partial = ""
        events = [
            StreamingTranscriptEvent(
                text=text.strip(),
                kind=StreamingTranscriptKind.FINAL,
                is_final=True,
                confidence=confidence,
                language=language,
                provider=self.provider,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        ]
        if self._speech_active:
            events.append(self.on_speech_end())
        return events


def _suffix_delta(previous: str, current: str) -> str:
    if not previous:
        return current
    if current.startswith(previous):
        return current[len(previous) :]
    # Provider rewrote the hypothesis — emit full current as delta
    return current


def _join_text(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()
    if not left:
        return right
    if not right:
        return left
    return f"{left} {right}"
