"""Redis pub/sub and polling hub for admin dashboard WebSocket updates."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

from api.constants import ADMIN_OPERATIONS_LIVE_POLL_S, ADMIN_OPERATIONS_LIVE_TTL_S, REDIS_URL
from api.enums import RedisChannel
from api.services.admin_operations.summary import AdminSummaryBuilder
from api.services.tenant.types import TenantContext


class AdminOperationsRealtimeHub:
    """Broadcasts dashboard snapshots to subscribed admin clients."""

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client
        self._summary = AdminSummaryBuilder()

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _channel(organization_id: int) -> str:
        return f"{RedisChannel.ADMIN_OPERATIONS_LIVE.value}:{organization_id}"

    async def publish_event(
        self,
        organization_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        redis = await self._get_redis()
        message = json.dumps(
            {
                "type": event_type,
                "organization_id": organization_id,
                "timestamp": time.time(),
                "payload": payload or {},
            }
        )
        await redis.publish(self._channel(organization_id), message)
        await redis.setex(
            f"admin_ops:last_event:{organization_id}",
            ADMIN_OPERATIONS_LIVE_TTL_S,
            message,
        )

    async def build_live_payload(
        self,
        ctx: TenantContext,
        *,
        days: int = 1,
    ) -> dict[str, Any]:
        summary = await self._summary.build(ctx, days=days)
        return {
            "type": "snapshot",
            "organization_id": ctx.organization_id,
            "timestamp": time.time(),
            "payload": summary,
        }

    async def stream_updates(
        self,
        ctx: TenantContext,
        *,
        days: int = 1,
        stop_event: asyncio.Event | None = None,
    ):
        """Async generator yielding snapshot and pub/sub events."""
        org_id = ctx.organization_id
        redis = await self._get_redis()
        pubsub = redis.pubsub()
        channel = self._channel(org_id)
        await pubsub.subscribe(channel)

        stop = stop_event or asyncio.Event()
        try:
            yield await self.build_live_payload(ctx, days=days)
            last_poll = time.monotonic()
            while not stop.is_set():
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message.get("type") == "message":
                    try:
                        yield json.loads(message["data"])
                    except json.JSONDecodeError:
                        logger.debug("ignored malformed admin_ops pubsub message")

                if time.monotonic() - last_poll >= ADMIN_OPERATIONS_LIVE_POLL_S:
                    yield await self.build_live_payload(ctx, days=days)
                    last_poll = time.monotonic()
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception as e:
                logger.debug("admin_ops pubsub cleanup: {}", e)


_hub: AdminOperationsRealtimeHub | None = None


def get_admin_operations_realtime_hub() -> AdminOperationsRealtimeHub:
    global _hub
    if _hub is None:
        _hub = AdminOperationsRealtimeHub()
    return _hub
