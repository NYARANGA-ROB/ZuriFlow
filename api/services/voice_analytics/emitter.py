from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from api.constants import VOICE_ANALYTICS_ENABLED
from api.services.voice_analytics.schema import normalize_event
from api.services.voice_analytics.types import VoiceAnalyticsEvent


class VoiceAnalyticsEmitter:
    """Non-blocking in-process event emitter."""

    def __init__(self, *, max_queue: int = 2048) -> None:
        self._queue: asyncio.Queue[VoiceAnalyticsEvent | None] = asyncio.Queue(maxsize=max_queue)
        self._worker: asyncio.Task | None = None
        self._handlers: list[Any] = []

    def register_handler(self, handler) -> None:
        self._handlers.append(handler)

    async def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._consume(), name="voice-analytics-emitter")

    async def stop(self) -> None:
        await self._queue.put(None)
        if self._worker:
            await self._worker

    def track(self, event: VoiceAnalyticsEvent) -> None:
        if not VOICE_ANALYTICS_ENABLED:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("voice analytics queue full, dropping event {}", event.event_type.value)

    async def track_async(self, event: VoiceAnalyticsEvent) -> None:
        if not VOICE_ANALYTICS_ENABLED:
            return
        await self._queue.put(event)

    def track_dict(self, data: dict[str, Any]) -> None:
        try:
            self.track(normalize_event(data))
        except ValueError as exc:
            logger.warning("invalid voice analytics event: {}", exc)

    async def _consume(self) -> None:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            for handler in self._handlers:
                try:
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    logger.exception(
                        "voice analytics handler failed for {}",
                        event.event_type.value,
                    )


_emitter: VoiceAnalyticsEmitter | None = None


def get_voice_analytics_emitter() -> VoiceAnalyticsEmitter:
    global _emitter
    if _emitter is None:
        _emitter = VoiceAnalyticsEmitter()
    return _emitter
