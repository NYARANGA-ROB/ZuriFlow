"""Bridge streaming STT to the voice_pipeline SpeechToTextService protocol."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from api.services.streaming_stt.realtime_service import RealtimeTranscriptionService
from api.services.streaming_stt.types import StreamingTranscriptKind
from api.services.voice_pipeline.types import AudioChunk, TranscriptEvent, TranscriptKind


class StreamingSTTBridge:
    """Adapts ``RealtimeTranscriptionService`` to ``SpeechToTextService``."""

    def __init__(self, service: RealtimeTranscriptionService) -> None:
        self._service = service
        self._relay_task: asyncio.Task | None = None
        self._queue: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()

    async def start(self) -> None:
        await self._service.start()
        self._relay_task = asyncio.create_task(self._relay_loop())

    async def stop(self) -> None:
        await self._service.stop()
        if self._relay_task:
            await self._relay_task
        await self._queue.put(None)

    async def push_audio(self, chunk: AudioChunk) -> None:
        await self._service.push_audio(chunk)

    async def interrupt(self) -> None:
        await self._service.interrupt()

    async def transcripts(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event

    async def _relay_loop(self) -> None:
        async for event in self._service.transcripts():
            if event.kind == StreamingTranscriptKind.SPEECH_START:
                kind = TranscriptKind.SPEECH_START
            elif event.kind in (
                StreamingTranscriptKind.PARTIAL,
                StreamingTranscriptKind.INCREMENTAL,
            ):
                kind = TranscriptKind.PARTIAL
            elif event.kind == StreamingTranscriptKind.FINAL:
                kind = TranscriptKind.FINAL
            else:
                continue
            if not event.text and kind not in (
                TranscriptKind.FINAL,
                TranscriptKind.SPEECH_START,
            ):
                continue
            te = TranscriptEvent(
                text=event.text,
                kind=kind,
                confidence=event.confidence,
                language=event.language,
            )
            try:
                self._queue.put_nowait(te)
            except asyncio.QueueFull:
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    self._queue.put_nowait(te)
                except asyncio.QueueFull:
                    pass