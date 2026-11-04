"""Bounded asyncio queues connecting pipeline stages."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TypeVar

from api.services.realtime_voice_pipeline.config import RealtimeVoicePipelineConfig
from api.services.realtime_voice_pipeline.types import PipelineControlEvent, PipelineControlKind, PipelineEvent
from api.services.voice_pipeline.types import AudioChunk, LLMStreamEvent, TranscriptEvent

T = TypeVar("T")


@dataclass
class PipelineQueues:
    """Queue graph for inbound audio → STT → LLM → TTS → outbound playback."""

    config: RealtimeVoicePipelineConfig
    inbound_audio: asyncio.Queue[AudioChunk | None] = field(init=False)
    transcript_events: asyncio.Queue[TranscriptEvent | None] = field(init=False)
    llm_events: asyncio.Queue[LLMStreamEvent | None] = field(init=False)
    outbound_audio: asyncio.Queue[AudioChunk | None] = field(init=False)
    control: asyncio.Queue[PipelineControlEvent | None] = field(init=False)
    pipeline_events: asyncio.Queue[PipelineEvent | None] = field(init=False)
    vad_events: asyncio.Queue = field(init=False)
    _outbound_dropped: int = 0

    def __post_init__(self) -> None:
        cfg = self.config
        self.inbound_audio = asyncio.Queue(maxsize=cfg.inbound_audio_maxsize)
        self.transcript_events = asyncio.Queue(maxsize=cfg.transcript_maxsize)
        self.llm_events = asyncio.Queue(maxsize=cfg.llm_event_maxsize)
        self.outbound_audio = asyncio.Queue(maxsize=cfg.outbound_audio_maxsize)
        self.control = asyncio.Queue(maxsize=cfg.control_maxsize)
        self.pipeline_events = asyncio.Queue(maxsize=cfg.llm_event_maxsize)
        self.vad_events = asyncio.Queue(maxsize=cfg.vad_events_maxsize)

    def put_nowait_drop(self, queue: asyncio.Queue, item: T) -> bool:
        """Non-blocking enqueue; drops oldest item when full (low-latency hot path)."""
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            return False

    def put_inbound(self, chunk: AudioChunk) -> bool:
        return self.put_nowait_drop(self.inbound_audio, chunk)

    def put_transcript(self, event: TranscriptEvent) -> bool:
        return self.put_nowait_drop(self.transcript_events, event)

    def put_outbound(self, chunk: AudioChunk) -> bool:
        ok = self.put_nowait_drop(self.outbound_audio, chunk)
        if not ok:
            self._outbound_dropped += 1
        return ok

    def put_vad(self, event) -> bool:
        return self.put_nowait_drop(self.vad_events, event)

    async def put_control(self, event: PipelineControlEvent) -> None:
        if event.kind == PipelineControlKind.SHUTDOWN:
            while not self.control.empty():
                try:
                    self.control.get_nowait()
                except asyncio.QueueEmpty:
                    break
            await self.control.put(event)
            return
        timeout = self.config.queue_put_timeout_s
        if timeout <= 0:
            self.put_nowait_drop(self.control, event)
            return
        try:
            await asyncio.wait_for(self.control.put(event), timeout=timeout)
        except asyncio.TimeoutError:
            pass

    def signal_stop(self) -> None:
        """Unblock handlers waiting on queue.get() during shutdown."""
        for queue in (
            self.inbound_audio,
            self.transcript_events,
            self.llm_events,
            self.outbound_audio,
            self.control,
            self.pipeline_events,
            self.vad_events,
        ):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

    def flush_outbound(self) -> int:
        flushed = 0
        while not self.outbound_audio.empty():
            try:
                self.outbound_audio.get_nowait()
                flushed += 1
            except asyncio.QueueEmpty:
                break
        return flushed

    @property
    def outbound_dropped(self) -> int:
        return self._outbound_dropped

    async def close(self) -> None:
        for queue in (
            self.inbound_audio,
            self.transcript_events,
            self.llm_events,
            self.outbound_audio,
            self.control,
            self.pipeline_events,
            self.vad_events,
        ):
            await queue.put(None)

    async def iter_inbound(self) -> AsyncIterator[AudioChunk]:
        while True:
            item = await self.inbound_audio.get()
            if item is None:
                break
            yield item

    async def iter_transcripts(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            item = await self.transcript_events.get()
            if item is None:
                break
            yield item

    async def iter_llm_events(self) -> AsyncIterator[LLMStreamEvent]:
        while True:
            item = await self.llm_events.get()
            if item is None:
                break
            yield item

    async def iter_outbound(self) -> AsyncIterator[AudioChunk]:
        while True:
            item = await self.outbound_audio.get()
            if item is None:
                break
            yield item

    async def iter_control(self) -> AsyncIterator[PipelineControlEvent]:
        while True:
            item = await self.control.get()
            if item is None:
                break
            yield item

    async def iter_vad_events(self):
        while True:
            item = await self.vad_events.get()
            if item is None:
                break
            yield item
