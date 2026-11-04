"""MediaTransport adapter over realtime_audio AudioSession queues."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from api.services.realtime_audio.connection_manager import AudioSession
from api.services.realtime_audio.server import drain_inbound_audio, enqueue_outbound_pcm
from api.services.voice_pipeline.streaming.interfaces import AudioInbound, AudioOutbound, MediaTransport
from api.services.voice_pipeline.types import AudioChunk, VoicePipelineConfig

OnOutboundChunk = Callable[[AudioChunk], Awaitable[None]]


class _SessionInbound:
    def __init__(self, session: AudioSession):
        self._session = session

    async def audio_chunks(self) -> AsyncIterator[AudioChunk]:
        async for frame in drain_inbound_audio(self._session):
            yield AudioChunk(
                pcm=frame.pcm,
                sample_rate=self._session.sample_rate,
                channels=self._session.channels,
                timestamp_ms=float(frame.timestamp_ms),
            )


class _SessionOutbound:
    def __init__(self, session: AudioSession):
        self._session = session

    async def send(self, chunk: AudioChunk) -> None:
        await enqueue_outbound_pcm(self._session, chunk.pcm)


class RealtimeAudioMediaTransport:
    """Bridges ``AudioSession`` queues to the voice pipeline ``MediaTransport`` protocol."""

    def __init__(self, session: AudioSession) -> None:
        self._session = session
        self._inbound = _SessionInbound(session)
        self._outbound = _SessionOutbound(session)
        self._relay_task: asyncio.Task | None = None
        self._out_queue: asyncio.Queue[AudioChunk | None] | None = None
        self._direct_outbound: OnOutboundChunk | None = None

    @property
    def session(self) -> AudioSession:
        return self._session

    async def open(
        self,
        config: VoicePipelineConfig,
        websocket: object = None,
        **kwargs: object,
    ) -> None:
        _ = config, websocket, kwargs

    async def close(self) -> None:
        if self._relay_task and not self._relay_task.done():
            self._relay_task.cancel()
            await asyncio.gather(self._relay_task, return_exceptions=True)

    def inbound(self) -> AudioInbound:
        return self._inbound

    def outbound(self) -> AudioOutbound:
        return self._outbound

    def bind_direct_outbound(self, callback: OnOutboundChunk) -> None:
        """Send synthesized audio directly to WebSocket — skips pipeline outbound queue."""
        self._direct_outbound = callback

    def bind_outbound_queue(self, queue: asyncio.Queue[AudioChunk | None]) -> None:
        """Fallback path: pump pipeline outbound queue into the WebSocket session."""
        self._out_queue = queue
        self._relay_task = asyncio.create_task(
            self._relay_outbound(), name="realtime-audio-outbound-relay"
        )

    async def emit_outbound(self, chunk: AudioChunk) -> None:
        """Hot-path outbound: direct callback when bound, else no-op (caller uses queue)."""
        if self._direct_outbound is not None:
            await self._direct_outbound(chunk)

    async def _relay_outbound(self) -> None:
        assert self._out_queue is not None
        outbound = self.outbound()
        while True:
            chunk = await self._out_queue.get()
            if chunk is None:
                break
            await outbound.send(chunk)
