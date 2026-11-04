"""Bounded asyncio queues for bidirectional audio streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from api.services.realtime_audio.config import RealtimeAudioConfig, DEFAULT_CONFIG
from api.services.realtime_audio.logging import log_chunk
from api.services.realtime_audio.protocol import AudioChunkFrame


@dataclass
class StreamStats:
    enqueued: int = 0
    dequeued: int = 0
    dropped: int = 0
    backpressure_events: int = 0


@dataclass
class BoundedAudioQueue:
    """Single-direction bounded queue with drop-on-saturation for inbound hot paths."""

    session_id: str
    direction: str
    maxsize: int
    put_timeout_s: float
    _queue: asyncio.Queue[AudioChunkFrame | None] = field(init=False)
    stats: StreamStats = field(default_factory=StreamStats)
    _closed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue(maxsize=self.maxsize)

    @property
    def closed(self) -> bool:
        return self._closed

    async def put(
        self,
        chunk: AudioChunkFrame,
        *,
        drop_if_full: bool = False,
    ) -> bool:
        """Enqueue a chunk. Returns False if dropped under backpressure."""
        if self._closed:
            return False

        if drop_if_full and self._queue.full():
            self.stats.dropped += 1
            self.stats.backpressure_events += 1
            log_chunk(
                self.session_id,
                direction=self.direction,
                seq=chunk.sequence,
                nbytes=chunk.nbytes,
                dropped=True,
            )
            return False

        try:
            await asyncio.wait_for(self._queue.put(chunk), timeout=self.put_timeout_s)
        except asyncio.TimeoutError:
            if drop_if_full:
                self.stats.dropped += 1
                self.stats.backpressure_events += 1
                log_chunk(
                    self.session_id,
                    direction=self.direction,
                    seq=chunk.sequence,
                    nbytes=chunk.nbytes,
                    dropped=True,
                )
                return False
            raise

        self.stats.enqueued += 1
        log_chunk(
            self.session_id,
            direction=self.direction,
            seq=chunk.sequence,
            nbytes=chunk.nbytes,
        )
        return True

    async def get(self) -> AudioChunkFrame | None:
        item = await self._queue.get()
        if item is None:
            return None
        self.stats.dequeued += 1
        return item

    def qsize(self) -> int:
        return self._queue.qsize()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Drain sentinel without blocking producers that already exited.
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        await self._queue.put(None)

    async def iter_chunks(self) -> AsyncIterator[AudioChunkFrame]:
        while True:
            chunk = await self.get()
            if chunk is None:
                break
            yield chunk


@dataclass
class BidirectionalStreamQueues:
    """Inbound (client → server) and outbound (server → client) audio queues."""

    session_id: str
    config: RealtimeAudioConfig = DEFAULT_CONFIG
    inbound: BoundedAudioQueue = field(init=False)
    outbound: BoundedAudioQueue = field(init=False)

    def __post_init__(self) -> None:
        self.inbound = BoundedAudioQueue(
            session_id=self.session_id,
            direction="inbound",
            maxsize=self.config.inbound_queue_maxsize,
            put_timeout_s=self.config.queue_put_timeout_s,
        )
        self.outbound = BoundedAudioQueue(
            session_id=self.session_id,
            direction="outbound",
            maxsize=self.config.outbound_queue_maxsize,
            put_timeout_s=self.config.queue_put_timeout_s,
        )

    async def close(self) -> None:
        await self.inbound.close()
        await self.outbound.close()
