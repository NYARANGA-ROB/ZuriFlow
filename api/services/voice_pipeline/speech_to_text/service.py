"""STT service implementations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from loguru import logger

from api.services.pipecat.audio_config import AudioConfig
from api.services.pipecat.service_factory import create_stt_service
from api.services.voice_pipeline.speech_to_text.interfaces import SpeechToTextService
from api.services.voice_pipeline.types import AudioChunk, TranscriptEvent, TranscriptKind


class PipecatSTTAdapter:
    """Wraps a Pipecat STT processor as an async push/pull service.

    Frame bridging runs in a background task; the public API stays non-blocking.
  """

    def __init__(
        self,
        *,
        user_config: object,
        audio_config: AudioConfig,
        keyterms: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self._user_config = user_config
        self._audio_config = audio_config
        self._keyterms = keyterms
        self._correlation_id = correlation_id
        self._stt = None
        self._transcript_queue: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._audio_queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    async def start(self) -> None:
        self._stt = create_stt_service(
            self._user_config,
            self._audio_config,
            keyterms=self._keyterms,
            correlation_id=self._correlation_id,
        )
        self._worker = asyncio.create_task(self._bridge_loop())
        logger.debug("PipecatSTTAdapter started")

    async def stop(self) -> None:
        await self._audio_queue.put(None)
        if self._worker:
            await self._worker
        await self._transcript_queue.put(None)

    async def push_audio(self, chunk: AudioChunk) -> None:
        await self._audio_queue.put(chunk)

    async def transcripts(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self._transcript_queue.get()
            if event is None:
                break
            yield event

    async def _bridge_loop(self) -> None:
        """Placeholder bridge — production path uses Pipecat frame processors directly.

        Modular orchestration can replace this with a frame-to-queue shim as
        Pipecat exposes async hooks per provider.
        """
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                break
            await asyncio.sleep(0)


class EchoSTTService:
    """Example STT that emits a final transcript after a short silence window."""

    def __init__(self, *, silence_chunks: int = 5) -> None:
        self._silence_chunks = silence_chunks
        self._buffer = bytearray()
        self._sample_rate = 16000
        self._chunks_since_audio = 0
        self._transcript_queue: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._audio_queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    async def start(self) -> None:
        self._worker = asyncio.create_task(self._process_loop())

    async def stop(self) -> None:
        await self._audio_queue.put(None)
        if self._worker:
            await self._worker
        await self._transcript_queue.put(None)

    async def push_audio(self, chunk: AudioChunk) -> None:
        await self._audio_queue.put(chunk)

    async def transcripts(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self._transcript_queue.get()
            if event is None:
                break
            yield event

    async def _process_loop(self) -> None:
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                break
            self._sample_rate = chunk.sample_rate
            self._buffer.extend(chunk.pcm)
            rms = _pcm_rms(chunk.pcm)
            if rms > 200:
                self._chunks_since_audio = 0
            else:
                self._chunks_since_audio += 1
            if self._chunks_since_audio >= self._silence_chunks and self._buffer:
                duration_s = len(self._buffer) / (2 * self._sample_rate)
                text = f"[heard {duration_s:.1f}s of audio]"
                await self._transcript_queue.put(
                    TranscriptEvent(text=text, kind=TranscriptKind.FINAL)
                )
                self._buffer.clear()
                self._chunks_since_audio = 0


def _pcm_rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    import struct

    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5
