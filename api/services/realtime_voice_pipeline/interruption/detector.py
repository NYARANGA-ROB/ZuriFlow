"""Detect caller barge-in from VAD and STT signals."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from api.services.realtime_voice_pipeline.config import RealtimeVoicePipelineConfig
from api.services.realtime_voice_pipeline.interruption.vad import VADEvent, VADEventKind
from api.services.voice_pipeline.types import TranscriptEvent, TranscriptKind


class InterruptionSource(str, Enum):
    VAD = "vad"
    STT_SPEECH_START = "stt_speech_start"
    STT_PARTIAL = "stt_partial"
    EXTERNAL = "external"


@dataclass(frozen=True)
class InterruptionEvent:
    source: InterruptionSource
    reason: str
    confidence: float = 1.0
    transcript: str = ""


@dataclass
class InterruptionDetector:
    """Fuse VAD + STT cues to decide when the caller has interrupted the bot."""

    config: RealtimeVoicePipelineConfig
    is_bot_active: Callable[[], bool]
    _last_interrupt_at: float | None = field(default=None, init=False)
    _vad_speech_active: bool = field(default=False, init=False)

    def on_vad(self, event: VADEvent) -> InterruptionEvent | None:
        if event.kind == VADEventKind.SPEECH_START:
            self._vad_speech_active = True
            if self.config.barge_in_on_vad and self._should_interrupt():
                return InterruptionEvent(
                    source=InterruptionSource.VAD,
                    reason="caller_speech_detected",
                    confidence=min(1.0, event.energy / max(self.config.vad_energy_threshold, 1.0)),
                )
        elif event.kind == VADEventKind.SPEECH_END:
            self._vad_speech_active = False
        return None

    def on_transcript(self, event: TranscriptEvent) -> InterruptionEvent | None:
        if event.kind == TranscriptKind.SPEECH_START:
            if self.config.barge_in_on_speech_start and self._should_interrupt():
                return InterruptionEvent(
                    source=InterruptionSource.STT_SPEECH_START,
                    reason="stt_speech_start",
                )
        if event.kind == TranscriptKind.PARTIAL:
            text = event.text.strip()
            if (
                self.config.barge_in_on_partial
                and len(text) >= self.config.min_partial_chars_for_barge_in
                and self._should_interrupt()
            ):
                return InterruptionEvent(
                    source=InterruptionSource.STT_PARTIAL,
                    reason="stt_partial",
                    transcript=text,
                    confidence=0.9,
                )
        return None

    def on_external(self, reason: str) -> InterruptionEvent:
        return InterruptionEvent(source=InterruptionSource.EXTERNAL, reason=reason)

    def mark_handled(self) -> None:
        self._last_interrupt_at = time.monotonic()

    def _should_interrupt(self) -> bool:
        if not self.is_bot_active():
            return False
        if self._in_cooldown():
            return False
        return True

    def _in_cooldown(self) -> bool:
        if self._last_interrupt_at is None:
            return False
        return (time.monotonic() - self._last_interrupt_at) < self.config.interrupt_cooldown_s
