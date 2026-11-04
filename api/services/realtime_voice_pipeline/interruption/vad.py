"""Energy-based voice activity detection on inbound PCM."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from enum import Enum


class VADEventKind(str, Enum):
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    SPEECH_ONGOING = "speech_ongoing"


@dataclass(frozen=True)
class VADConfig:
    """Tunable thresholds for lightweight RMS voice activity detection."""

    energy_threshold: float = 450.0
    min_speech_frames: int = 2
    hangover_frames: int = 6
    frame_ms: float = 20.0


@dataclass(frozen=True)
class VADEvent:
    kind: VADEventKind
    energy: float
    timestamp_ms: float | None = None


@dataclass
class VoiceActivityDetector:
    """Detect caller speech from PCM int16 frames using RMS energy."""

    config: VADConfig = VADConfig()
    _speech_frames: int = 0
    _silence_frames: int = 0
    _in_speech: bool = False
    _elapsed_ms: float = 0.0

    def process(self, pcm: bytes, *, sample_rate: int, timestamp_ms: float | None = None) -> list[VADEvent]:
        if not pcm:
            return []

        ts = timestamp_ms if timestamp_ms is not None else self._elapsed_ms
        frame_samples = max(1, int(sample_rate * self.config.frame_ms / 1000))
        frame_bytes = frame_samples * 2
        events: list[VADEvent] = []

        for offset in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
            frame = pcm[offset : offset + frame_bytes]
            energy = self._rms_energy(frame)
            ts += self.config.frame_ms
            self._elapsed_ms = ts

            if energy >= self.config.energy_threshold:
                self._speech_frames += 1
                self._silence_frames = 0
                if not self._in_speech and self._speech_frames >= self.config.min_speech_frames:
                    self._in_speech = True
                    events.append(
                        VADEvent(kind=VADEventKind.SPEECH_START, energy=energy, timestamp_ms=ts)
                    )
                elif self._in_speech:
                    events.append(
                        VADEvent(
                            kind=VADEventKind.SPEECH_ONGOING,
                            energy=energy,
                            timestamp_ms=ts,
                        )
                    )
            else:
                self._silence_frames += 1
                self._speech_frames = 0
                if self._in_speech and self._silence_frames >= self.config.hangover_frames:
                    self._in_speech = False
                    events.append(
                        VADEvent(kind=VADEventKind.SPEECH_END, energy=energy, timestamp_ms=ts)
                    )

        return events

    def reset(self) -> None:
        self._speech_frames = 0
        self._silence_frames = 0
        self._in_speech = False

    @staticmethod
    def _rms_energy(pcm: bytes) -> float:
        count = len(pcm) // 2
        if count == 0:
            return 0.0
        samples = struct.unpack(f"<{count}h", pcm[: count * 2])
        mean_sq = sum(s * s for s in samples) / count
        return math.sqrt(mean_sq)
