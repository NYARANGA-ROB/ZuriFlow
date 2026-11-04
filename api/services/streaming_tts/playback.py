"""Streaming playback handler — drains TTS events through the audio buffer."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

from loguru import logger

from api.services.streaming_tts.buffering import AudioBufferService
from api.services.streaming_tts.cancellation import CancellationRegistry
from api.services.streaming_tts.types import TTSStreamEvent, TTSStreamKind
from api.services.voice_pipeline.types import AudioChunk

OnPlaybackChunk = Callable[[AudioChunk], Awaitable[None]]


@dataclass
class StreamingPlaybackHandler:
    """Consumes TTS stream events and plays audio with jitter buffering."""

    session_id: str
    buffer: AudioBufferService
    on_chunk: OnPlaybackChunk | None = None
    cancellations: CancellationRegistry = field(default_factory=CancellationRegistry)
    _playback_task: asyncio.Task | None = None
    _active_generation: str | None = None

    async def start(self) -> None:
        self._playback_task = asyncio.create_task(
            self._playback_loop(), name=f"tts-playback-{self.session_id[:8]}"
        )

    async def stop(self) -> None:
        await self.buffer.close()
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
            await asyncio.gather(self._playback_task, return_exceptions=True)

    async def handle_event(self, event: TTSStreamEvent) -> None:
        if event.kind == TTSStreamKind.SYNTHESIS_START:
            self._active_generation = event.generation_id
            self.buffer.set_generation(event.generation_id)
            self.cancellations.create(event.generation_id)
            return

        if event.kind == TTSStreamKind.CANCELLED:
            if (
                self._active_generation is None
                or event.generation_id == self._active_generation
            ):
                await self.interrupt(event.generation_id)
            return

        if event.kind == TTSStreamKind.SYNTHESIS_END:
            await self.buffer.flush()
            self.cancellations.release(event.generation_id)
            if self._active_generation == event.generation_id:
                self._active_generation = None
            return

        if event.kind == TTSStreamKind.ERROR:
            logger.warning(
                "streaming_tts playback error session={} meta={}",
                self.session_id,
                event.metadata,
            )
            return

        if event.kind == TTSStreamKind.AUDIO_CHUNK:
            token = self.cancellations.get(event.generation_id)
            if token and token.is_cancelled:
                return
            await self.buffer.push_event(event)

    async def interrupt(self, generation_id: str | None = None) -> None:
        """Cancel playback and clear buffered audio."""
        self.cancellations.cancel(generation_id)
        self.buffer.clear()
        if generation_id is None or self._active_generation == generation_id:
            self._active_generation = None

    async def play_stream(self, events: AsyncIterator[TTSStreamEvent]) -> None:
        async for event in events:
            await self.handle_event(event)

    async def _playback_loop(self) -> None:
        try:
            async for chunk in self.buffer.drain():
                if self.on_chunk is not None:
                    await self.on_chunk(chunk)
        except asyncio.CancelledError:
            pass


def new_generation_id() -> str:
    return uuid.uuid4().hex
