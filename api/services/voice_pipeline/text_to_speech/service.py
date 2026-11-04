"""TTS service implementations."""

from __future__ import annotations

import asyncio
import math
import struct
from collections.abc import AsyncIterator

from api.services.pipecat.audio_config import AudioConfig
from api.services.pipecat.service_factory import create_tts_service
from api.services.voice_pipeline.text_to_speech.interfaces import TextToSpeechService
from api.services.voice_pipeline.types import AudioChunk, TTSRequest


class PipecatTTSAdapter:
    """Factory wrapper for Pipecat TTS services."""

    def __init__(
        self,
        *,
        user_config: object,
        audio_config: AudioConfig,
        correlation_id: str | None = None,
    ) -> None:
        self._user_config = user_config
        self._audio_config = audio_config
        self._correlation_id = correlation_id
        self._tts = None

    async def start(self) -> None:
        self._tts = create_tts_service(
            self._user_config,
            self._audio_config,
            correlation_id=self._correlation_id,
        )

    async def stop(self) -> None:
        self._tts = None

    async def synthesize(self, request: TTSRequest) -> AsyncIterator[AudioChunk]:
        _ = request
        if self._tts is None:
            raise RuntimeError("PipecatTTSAdapter.start() not called")
        if False:
            yield AudioChunk(pcm=b"", sample_rate=16000)


class ToneTTSService:
    """Example TTS that emits a short sine tone per word."""

    def __init__(self, *, sample_rate: int = 16000, tone_hz: float = 440.0) -> None:
        self._sample_rate = sample_rate
        self._tone_hz = tone_hz

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def synthesize(self, request: TTSRequest) -> AsyncIterator[AudioChunk]:
        sample_rate = request.sample_rate or self._sample_rate
        words = request.text.split() or ["."]
        for word in words:
            duration_s = min(0.15 + len(word) * 0.02, 0.8)
            pcm = _sine_pcm(sample_rate, self._tone_hz, duration_s)
            yield AudioChunk(pcm=pcm, sample_rate=sample_rate)
            await asyncio.sleep(0)


def _sine_pcm(sample_rate: int, frequency: float, duration_s: float) -> bytes:
    n_samples = int(sample_rate * duration_s)
    amplitude = 8000
    samples = [
        int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
        for i in range(n_samples)
    ]
    return struct.pack(f"<{n_samples}h", *samples)
