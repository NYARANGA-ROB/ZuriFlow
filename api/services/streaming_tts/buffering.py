"""Low-latency audio buffering with jitter pre-roll."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from queue import Empty

from loguru import logger

from api.services.streaming_tts.config import StreamingTTSConfig, DEFAULT_STREAMING_TTS_CONFIG
from api.services.streaming_tts.types import TTSStreamEvent, TTSStreamKind
from api.services.voice_pipeline.types import AudioChunk


@dataclass
class AudioBufferService:
    """Bounded jitter buffer that releases audio once a minimum pre-roll is met."""

    session_id: str
    config: StreamingTTSConfig = DEFAULT_STREAMING_TTS_CONFIG
    _queue: asyncio.Queue[AudioChunk | None] = field(init=False)
    _preroll: list[AudioChunk] = field(default_factory=list, init=False)
    _preroll_bytes: int = 0
    _playback_started: bool = False
    _closed: bool = False
    _generation_id: str = ""

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue(maxsize=self.config.audio_queue_maxsize)

    @property
    def min_preroll_bytes(self) -> int:
        ms = self.config.min_playback_buffer_ms
        return int(self.config.sample_rate * 2 * ms / 1000)

    @property
    def max_preroll_bytes(self) -> int:
        ms = self.config.max_playback_buffer_ms
        return int(self.config.sample_rate * 2 * ms / 1000)

    def set_generation(self, generation_id: str) -> None:
        self._generation_id = generation_id

    async def push_event(self, event: TTSStreamEvent) -> None:
        if self._closed:
            return
        if event.kind != TTSStreamKind.AUDIO_CHUNK or not event.audio:
            return
        if len(event.audio) > self.config.max_chunk_bytes:
            logger.warning(
                "streaming_tts chunk too large session={} bytes={}",
                self.session_id,
                len(event.audio),
            )
            return

        chunk = AudioChunk(
            pcm=event.audio,
            sample_rate=event.sample_rate or self.config.sample_rate,
            timestamp_ms=time.monotonic() * 1000,
        )

        if not self._playback_started:
            self._preroll.append(chunk)
            self._preroll_bytes += len(event.audio)
            if self._preroll_bytes >= self.min_preroll_bytes:
                await self._flush_preroll()
            elif self._preroll_bytes >= self.max_preroll_bytes:
                await self._flush_preroll()
            return

        await self._enqueue(chunk)

    async def _flush_preroll(self) -> None:
        self._playback_started = True
        for chunk in self._preroll:
            await self._enqueue(chunk)
        self._preroll.clear()
        self._preroll_bytes = 0

    async def _enqueue(self, chunk: AudioChunk) -> None:
        timeout = self.config.queue_put_timeout_s
        if timeout <= 0:
            try:
                self._queue.put_nowait(chunk)
            except asyncio.QueueFull:
                try:
                    self._queue.get_nowait()
                except Empty:
                    pass
                try:
                    self._queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass
            return
        try:
            await asyncio.wait_for(self._queue.put(chunk), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "streaming_tts playback buffer saturated session={}", self.session_id
            )

    async def flush(self) -> None:
        """Release any remaining pre-roll without waiting for min threshold."""
        if self._preroll:
            await self._flush_preroll()

    def clear(self) -> None:
        """Interrupt: drop buffered audio immediately."""
        self._preroll.clear()
        self._preroll_bytes = 0
        self._playback_started = False
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break

    async def close(self) -> None:
        self._closed = True
        await self.flush()
        await self._queue.put(None)

    async def drain(self) -> AsyncIterator[AudioChunk]:
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                break
            yield chunk
