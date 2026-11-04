"""Bridge streaming TTS to the voice_pipeline TextToSpeechService protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator

from api.services.streaming_tts.realtime_service import RealtimeStreamingTTSService
from api.services.voice_pipeline.types import AudioChunk, TTSRequest


class StreamingTTSBridge:
    """Adapts ``RealtimeStreamingTTSService`` to ``TextToSpeechService``."""

    def __init__(self, service: RealtimeStreamingTTSService) -> None:
        self._service = service

    async def start(self) -> None:
        await self._service.start()

    async def stop(self) -> None:
        await self._service.stop()

    async def interrupt(self) -> None:
        await self._service.interrupt()

    async def synthesize(self, request: TTSRequest) -> AsyncIterator[AudioChunk]:
        async for chunk in self._service.stream_utterance(request.text):
            if request.sample_rate and chunk.sample_rate != request.sample_rate:
                yield AudioChunk(
                    pcm=chunk.pcm,
                    sample_rate=request.sample_rate,
                    channels=chunk.channels,
                    timestamp_ms=chunk.timestamp_ms,
                )
            else:
                yield chunk

    async def push_text_delta(self, delta: str, *, generation_id: str | None = None) -> str:
        gid = generation_id
        if not gid:
            gid = await self._service.begin_synthesis()
        await self._service.push_text(delta, generation_id=gid)
        return gid

    async def begin_synthesis(self, generation_id: str | None = None) -> str:
        return await self._service.begin_synthesis(generation_id)

    async def end_synthesis(self, generation_id: str | None = None) -> None:
        await self._service.end_synthesis(generation_id)

    def register_generation_sink(self, generation_id: str):
        return self._service.register_generation_sink(generation_id)

    def release_generation_sink(self, generation_id: str) -> None:
        self._service.release_generation_sink(generation_id)
