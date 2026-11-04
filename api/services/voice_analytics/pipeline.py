from __future__ import annotations

import asyncio

from loguru import logger

from api.constants import POSTHOG_API_KEY, POSTHOG_HOST
from api.services.voice_analytics.emitter import get_voice_analytics_emitter
from api.services.voice_analytics.store import VoiceAnalyticsStore
from api.services.voice_analytics.types import VoiceAnalyticsEvent

_posthog_client = None
_posthog_lock = asyncio.Lock()


class VoiceAnalyticsPipeline:
    """Async pipeline: emitter -> Redis store -> optional PostHog (non-blocking)."""

    def __init__(self, store: VoiceAnalyticsStore | None = None) -> None:
        self._store = store or VoiceAnalyticsStore()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        emitter = get_voice_analytics_emitter()
        emitter.register_handler(self._ingest_local)
        await emitter.start()
        self._started = True

    async def stop(self) -> None:
        emitter = get_voice_analytics_emitter()
        await emitter.stop()
        self._started = False

    async def ingest(self, event: VoiceAnalyticsEvent) -> None:
        await self._store.append_event(event)

    async def _ingest_local(self, event: VoiceAnalyticsEvent) -> None:
        await self._store.append_event(event)
        if POSTHOG_API_KEY:
            asyncio.create_task(
                self.forward_posthog(event),
                name=f"posthog-{event.event_type.value}",
            )

    @staticmethod
    async def forward_posthog(event: VoiceAnalyticsEvent) -> None:
        if not POSTHOG_API_KEY:
            return
        try:
            import httpx

            global _posthog_client
            async with _posthog_lock:
                if _posthog_client is None:
                    _posthog_client = httpx.AsyncClient(timeout=5.0)

            payload = {
                "api_key": POSTHOG_API_KEY,
                "event": f"voice_{event.event_type.value}",
                "distinct_id": event.session_id or f"org-{event.organization_id}",
                "properties": {
                    **event.to_dict(),
                    "$lib": "dograh-voice-analytics",
                },
            }
            await _posthog_client.post(f"{POSTHOG_HOST}/capture/", json=payload)
        except Exception:
            logger.debug("PostHog forward skipped for {}", event.event_type.value)


_pipeline: VoiceAnalyticsPipeline | None = None


def get_voice_analytics_pipeline() -> VoiceAnalyticsPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = VoiceAnalyticsPipeline()
    return _pipeline
