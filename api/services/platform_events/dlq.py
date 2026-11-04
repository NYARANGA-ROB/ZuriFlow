"""Dead-letter queue for failed platform event handler deliveries."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from api.constants import PLATFORM_EVENTS_DLQ_TTL_S, REDIS_URL
from api.services.platform_events.schema import PlatformEvent


class PlatformEventDLQ:
    """Tenant-scoped DLQ for exhausted handler retries."""

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _org_key(organization_id: int | None) -> str:
        org = organization_id if organization_id is not None else 0
        return f"platform_events:dlq:{org}"

    @staticmethod
    def _retry_key(organization_id: int | None) -> str:
        org = organization_id if organization_id is not None else 0
        return f"platform_events:retry:{org}"

    async def enqueue(
        self,
        event: PlatformEvent,
        *,
        handler_name: str,
        error: str,
        attempts: int,
    ) -> str:
        entry_id = str(uuid.uuid4())
        payload = {
            "dlq_id": entry_id,
            "enqueued_at": time.time(),
            "handler_name": handler_name,
            "error": error,
            "attempts": attempts,
            "event": event.to_dict(),
        }
        redis = await self._get_redis()
        key = self._org_key(event.organization_id)
        raw = json.dumps(payload, separators=(",", ":"))
        pipe = redis.pipeline()
        pipe.lpush(key, raw)
        pipe.ltrim(key, 0, 999)
        pipe.expire(key, PLATFORM_EVENTS_DLQ_TTL_S)
        await pipe.execute()
        return entry_id

    async def list_entries(
        self,
        organization_id: int,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        raw_items = await redis.lrange(self._org_key(organization_id), 0, limit - 1)
        entries: list[dict[str, Any]] = []
        for raw in raw_items:
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return entries

    async def depth(self, organization_id: int) -> int:
        redis = await self._get_redis()
        return int(await redis.llen(self._org_key(organization_id)))

    async def schedule_retry(
        self,
        event: PlatformEvent,
        *,
        handler_name: str,
        attempt: int,
        delay_s: float,
    ) -> None:
        redis = await self._get_redis()
        run_at = time.time() + max(0.0, delay_s)
        payload = json.dumps(
            {
                "event_id": event.event_id,
                "handler_name": handler_name,
                "attempt": attempt,
            },
            separators=(",", ":"),
        )
        await redis.zadd(self._retry_key(event.organization_id), {payload: run_at})

    async def claim_due_retries(
        self,
        organization_id: int,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        key = self._retry_key(organization_id)
        now = time.time()
        raw_items = await redis.zrangebyscore(key, "-inf", now, start=0, num=limit)
        claimed: list[dict[str, Any]] = []
        for raw in raw_items:
            try:
                item = json.loads(raw)
                claimed.append(item)
                await redis.zrem(key, raw)
            except json.JSONDecodeError:
                await redis.zrem(key, raw)
        return claimed

    async def scan_organization_ids_with_retries(self) -> list[int]:
        redis = await self._get_redis()
        org_ids: set[int] = set()
        async for key in redis.scan_iter(match="platform_events:retry:*", count=100):
            try:
                org_ids.add(int(key.rsplit(":", 1)[-1]))
            except ValueError:
                continue
        return sorted(org_ids)


_dlq: PlatformEventDLQ | None = None


def get_platform_event_dlq() -> PlatformEventDLQ:
    global _dlq
    if _dlq is None:
        _dlq = PlatformEventDLQ()
    return _dlq
