"""Metrics and tracing hooks for platform events."""

from __future__ import annotations

import time
from typing import Any

import redis.asyncio as aioredis

from api.constants import REDIS_URL
from api.services.platform_events.schema import PlatformEvent


class PlatformEventObservability:
    """Lightweight Redis counters for event throughput and failures."""

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _counter_key(organization_id: int | None, suffix: str) -> str:
        org = organization_id if organization_id is not None else 0
        return f"platform_events:metrics:{org}:{suffix}"

    async def record_published(self, event: PlatformEvent) -> None:
        redis = await self._get_redis()
        pipe = redis.pipeline()
        pipe.incr(self._counter_key(event.organization_id, "published"))
        pipe.incr(
            self._counter_key(
                event.organization_id,
                f"type:{event.event_type.value}:published",
            )
        )
        pipe.set(
            self._counter_key(event.organization_id, "last_published_at"),
            str(time.time()),
        )
        await pipe.execute()

    async def record_handled(
        self,
        event: PlatformEvent,
        *,
        handler_name: str,
    ) -> None:
        redis = await self._get_redis()
        pipe = redis.pipeline()
        pipe.incr(self._counter_key(event.organization_id, "handled"))
        pipe.incr(
            self._counter_key(
                event.organization_id,
                f"handler:{handler_name}:ok",
            )
        )
        await pipe.execute()

    async def record_failed(
        self,
        event: PlatformEvent,
        *,
        handler_name: str,
        error: str,
    ) -> None:
        redis = await self._get_redis()
        pipe = redis.pipeline()
        pipe.incr(self._counter_key(event.organization_id, "failed"))
        pipe.incr(
            self._counter_key(
                event.organization_id,
                f"handler:{handler_name}:failed",
            )
        )
        await pipe.execute()

    async def snapshot(self, organization_id: int) -> dict[str, Any]:
        redis = await self._get_redis()
        pattern = self._counter_key(organization_id, "*")
        # Scan matching keys for this org prefix
        prefix = f"platform_events:metrics:{organization_id}:"
        counters: dict[str, int] = {}
        async for key in redis.scan_iter(match=f"{prefix}*", count=200):
            short = key.removeprefix(prefix)
            try:
                counters[short] = int(await redis.get(key) or 0)
            except ValueError:
                continue
        last = await redis.get(self._counter_key(organization_id, "last_published_at"))
        return {
            "organization_id": organization_id,
            "counters": counters,
            "last_published_at": float(last) if last else None,
        }


_obs: PlatformEventObservability | None = None


def get_platform_event_observability() -> PlatformEventObservability:
    global _obs
    if _obs is None:
        _obs = PlatformEventObservability()
    return _obs
