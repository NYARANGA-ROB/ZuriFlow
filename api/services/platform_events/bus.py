"""Central platform event bus."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

from api.constants import PLATFORM_EVENTS_ENABLED, REDIS_URL
from api.db import db_client
from api.enums import RedisChannel
from api.services.platform_events.schema import PlatformEvent
from api.tasks.function_names import FunctionNames


class PlatformEventBus:
    """Persist, publish, and enqueue platform events for async routing."""

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @property
    def enabled(self) -> bool:
        return PLATFORM_EVENTS_ENABLED

    async def publish(
        self,
        event: PlatformEvent,
        *,
        route_async: bool = True,
    ) -> dict[str, Any]:
        """Persist event idempotently, fan-out via Redis, optionally enqueue routing."""
        if not self.enabled:
            return {"published": False, "reason": "disabled"}

        source = (
            event.source.value
            if hasattr(event.source, "value")
            else str(event.source)
        )
        row = await db_client.insert_platform_event(
            event_id=event.event_id,
            organization_id=event.organization_id,
            event_type=event.event_type.value,
            source=source,
            correlation_id=event.correlation_id,
            payload=event.payload,
            idempotency_key=event.idempotency_key,
        )
        if row is None:
            if event.idempotency_key:
                existing = await db_client.get_platform_event_by_idempotency_key(
                    event.idempotency_key
                )
                if existing:
                    return {
                        "published": True,
                        "deduplicated": True,
                        "event_id": existing.event_id,
                        "db_id": existing.id,
                    }
            return {"published": False, "reason": "insert_failed"}

        serialized = json.dumps(event.to_dict(), separators=(",", ":"))
        redis = await self._get_redis()
        await redis.publish(RedisChannel.PLATFORM_EVENTS.value, serialized)

        from api.services.platform_events.observability import get_platform_event_observability

        await get_platform_event_observability().record_published(event)

        if route_async:
            await self._enqueue_route(row.event_id)
        else:
            from api.services.platform_events.router import get_platform_event_router

            await get_platform_event_router().dispatch(PlatformEvent.from_db_row(row))

        logger.debug(
            "platform event published type={} org={} event_id={}",
            event.event_type.value,
            event.organization_id,
            event.event_id,
        )
        return {
            "published": True,
            "event_id": row.event_id,
            "db_id": row.id,
            "deduplicated": False,
        }

    async def publish_dict(
        self,
        data: dict[str, Any],
        *,
        route_async: bool = True,
    ) -> dict[str, Any]:
        return await self.publish(
            PlatformEvent.from_dict(data),
            route_async=route_async,
        )

    async def _enqueue_route(self, event_id: str) -> None:
        from api.tasks.arq import get_arq_redis

        redis = await get_arq_redis()
        await redis.enqueue_job(
            FunctionNames.ROUTE_PLATFORM_EVENT,
            event_id,
        )


_bus: PlatformEventBus | None = None


def get_platform_event_bus() -> PlatformEventBus:
    global _bus
    if _bus is None:
        _bus = PlatformEventBus()
    return _bus
