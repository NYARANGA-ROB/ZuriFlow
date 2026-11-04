"""Immediately stop TTS playback and flush pending outbound audio."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from api.services.realtime_voice_pipeline.queues import PipelineQueues
from api.services.voice_pipeline.text_to_speech.streaming_adapter import StreamingTTSBridge


@dataclass
class TTSStopHandler:
    """Hard-stops synthesis and clears queued playback audio."""

    tts: StreamingTTSBridge
    queues: PipelineQueues
    _active_generation_id: str | None = field(default=None, init=False)
    _active_sink: asyncio.Queue | None = field(default=None, init=False)

    def track_generation(
        self, generation_id: str, sink: asyncio.Queue | None = None
    ) -> None:
        self._active_generation_id = generation_id
        self._active_sink = sink

    def clear_tracking(self) -> None:
        self._active_generation_id = None
        self._active_sink = None

    async def stop_immediately(self, generation_id: str | None = None) -> dict[str, Any]:
        """Cancel TTS, release sink, and drain outbound audio queue."""
        gid = generation_id or self._active_generation_id
        flushed = self.queues.flush_outbound()

        try:
            await self.tts.interrupt()
        except Exception as e:
            logger.warning("TTS stop interrupt failed: {}", e)

        if gid:
            try:
                await self.tts.end_synthesis(gid)
            except Exception:
                pass
            self.tts.release_generation_sink(gid)

        if self._active_sink is not None:
            while not self._active_sink.empty():
                try:
                    self._active_sink.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self._active_sink.put_nowait(None)

        self.clear_tracking()
        return {"generation_id": gid, "flushed_chunks": flushed, "stopped": True}
