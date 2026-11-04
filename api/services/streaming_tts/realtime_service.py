"""Low-latency streaming TTS orchestration service."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from loguru import logger

from api.services.streaming_tts.buffering import AudioBufferService
from api.services.streaming_tts.cancellation import CancellationRegistry
from api.services.streaming_tts.clients.elevenlabs import ElevenLabsStreamingClient
from api.services.streaming_tts.config import StreamingTTSConfig, DEFAULT_STREAMING_TTS_CONFIG
from api.services.streaming_tts.errors import ElevenLabsConnectionError
from api.services.streaming_tts.playback import StreamingPlaybackHandler
from api.services.streaming_tts.types import TextFragment, TTSStreamEvent, TTSStreamKind
from api.services.voice_pipeline.types import AudioChunk

OnPlaybackChunk = Callable[[AudioChunk], Awaitable[None]]


class RealtimeStreamingTTSService:
    """Streams incremental text to ElevenLabs and plays PCM with interruption support."""

    def __init__(
        self,
        *,
        api_key: str,
        config: StreamingTTSConfig,
        session_id: str | None = None,
        client: ElevenLabsStreamingClient | None = None,
        on_playback_chunk: OnPlaybackChunk | None = None,
    ) -> None:
        self._config = config
        self._session_id = session_id or uuid.uuid4().hex
        self._cancellations = CancellationRegistry()
        self._client = client or ElevenLabsStreamingClient(
            api_key=api_key,
            config=config,
            cancellations=self._cancellations,
        )
        self._buffer = AudioBufferService(self._session_id, config)
        self._playback = StreamingPlaybackHandler(
            session_id=self._session_id,
            buffer=self._buffer,
            on_chunk=on_playback_chunk,
            cancellations=self._cancellations,
        )
        self._text_queue: asyncio.Queue[TextFragment | None] = asyncio.Queue(
            maxsize=config.text_queue_maxsize
        )
        self._out_events: asyncio.Queue[TTSStreamEvent | None] = asyncio.Queue(
            maxsize=config.audio_queue_maxsize
        )
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._current_generation: str | None = None
        self._generation_sinks: dict[str, asyncio.Queue[AudioChunk | None]] = {}

    def register_generation_sink(
        self, generation_id: str
    ) -> asyncio.Queue[AudioChunk | None]:
        sink: asyncio.Queue[AudioChunk | None] = asyncio.Queue(
            maxsize=self._config.audio_queue_maxsize
        )
        self._generation_sinks[generation_id] = sink
        return sink

    def _put_sink_chunk(
        self, sink: asyncio.Queue[AudioChunk | None], chunk: AudioChunk
    ) -> None:
        try:
            sink.put_nowait(chunk)
        except asyncio.QueueFull:
            try:
                sink.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                sink.put_nowait(chunk)
            except asyncio.QueueFull:
                logger.debug("tts generation sink saturated")

    def release_generation_sink(self, generation_id: str) -> None:
        sink = self._generation_sinks.pop(generation_id, None)
        if sink is not None:
            sink.put_nowait(None)

    async def stream_utterance(self, text: str) -> AsyncIterator[AudioChunk]:
        """Synthesize one utterance and yield audio chunks until complete."""
        gid = await self.begin_synthesis()
        sink = self.register_generation_sink(gid)
        if text:
            await self.push_text(text, generation_id=gid)
        await self.end_synthesis(gid)

        try:
            while True:
                chunk = await sink.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            self.release_generation_sink(gid)

    async def start(self) -> None:
        await self._client.connect()
        if self._playback.on_chunk is not None:
            await self._playback.start()
        self._tasks = [
            asyncio.create_task(self._text_pump(), name="tts-text-pump"),
            asyncio.create_task(self._client_events_loop(), name="tts-client-events"),
        ]

    async def stop(self) -> None:
        self._stop.set()
        await self._text_queue.put(None)
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._client.close()
        await self._playback.stop()
        await self._out_events.put(None)

    async def begin_synthesis(self, generation_id: str | None = None) -> str:
        gid = generation_id or uuid.uuid4().hex
        self._current_generation = gid
        await self._client.begin_utterance(gid)
        return gid

    async def push_text(
        self,
        text: str,
        *,
        generation_id: str | None = None,
        is_final: bool = False,
    ) -> None:
        """Push incremental LLM text for partial-response playback."""
        gid = generation_id or self._current_generation
        if not gid:
            gid = await self.begin_synthesis()
        fragment = TextFragment(text=text, generation_id=gid, is_final=is_final)
        try:
            await asyncio.wait_for(
                self._text_queue.put(fragment),
                timeout=self._config.queue_put_timeout_s,
            )
        except asyncio.TimeoutError:
            logger.warning("streaming_tts text queue saturated")

    async def end_synthesis(self, generation_id: str | None = None) -> None:
        gid = generation_id or self._current_generation
        if gid:
            await self._client.end_utterance(gid)

    async def synthesize(self, text: str) -> str:
        """Convenience: synthesize a complete utterance from full text."""
        gid = await self.begin_synthesis()
        await self.push_text(text, generation_id=gid)
        await self.end_synthesis(gid)
        return gid

    async def interrupt(self, generation_id: str | None = None) -> None:
        """Barge-in: cancel synthesis, clear buffer, stop playback."""
        await self._client.cancel(generation_id)
        await self._playback.interrupt(generation_id)
        if generation_id is None or self._current_generation == generation_id:
            self._current_generation = None

    def events(self) -> AsyncIterator[TTSStreamEvent]:
        return self._iter_events()

    def audio_chunks(self) -> AsyncIterator[AudioChunk]:
        return self._buffer.drain()

    async def _iter_events(self) -> AsyncIterator[TTSStreamEvent]:
        while True:
            event = await self._out_events.get()
            if event is None:
                break
            yield event

    async def _text_pump(self) -> None:
        while not self._stop.is_set():
            fragment = await self._text_queue.get()
            if fragment is None:
                break
            try:
                await self._client.push_text(fragment)
                if fragment.is_final:
                    await self._client.end_utterance(fragment.generation_id)
            except Exception as e:
                logger.warning("streaming_tts push_text failed: {}", e)

    async def _client_events_loop(self) -> None:
        try:
            async for event in self._client.events():
                await self._out_events.put(event)
                await self._playback.handle_event(event)
                if event.kind == TTSStreamKind.AUDIO_CHUNK and event.audio:
                    sink = self._generation_sinks.get(event.generation_id)
                    if sink is not None:
                        self._put_sink_chunk(
                            sink,
                            AudioChunk(
                                pcm=event.audio,
                                sample_rate=event.sample_rate or self._config.sample_rate,
                            ),
                        )
                elif event.kind in (
                    TTSStreamKind.SYNTHESIS_END,
                    TTSStreamKind.CANCELLED,
                ):
                    self.release_generation_sink(event.generation_id)
        except asyncio.CancelledError:
            pass
