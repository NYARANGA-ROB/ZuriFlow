"""Redis-backed priority queue for outbound collection calls."""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

from api.constants import REDIS_URL
from api.services.call_prioritization.types import PrioritizedCallEntry, RetrySchedule


class PrioritizationQueue:
    """Sorted-set queue — higher score dequeues first."""

    def __init__(self, redis_client: aioredis.Redis | None = None, *, ttl_s: int = 86400) -> None:
        self._redis = redis_client
        self._ttl_s = ttl_s

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _queue_key(organization_id: int) -> str:
        return f"call_prioritization:queue:{organization_id}"

    @staticmethod
    def _entry_key(organization_id: int, customer_id: int) -> str:
        return f"call_prioritization:entry:{organization_id}:{customer_id}"

    async def enqueue(self, entry: PrioritizedCallEntry) -> tuple[bool, int]:
        redis = await self._get_redis()
        queue_key = self._queue_key(entry.organization_id)
        entry_key = self._entry_key(entry.organization_id, entry.customer_id)

        if entry.enqueued_at <= 0:
            entry.enqueued_at = time.time()

        payload = json.dumps(entry.to_dict())
        # Higher score first; tiny time tie-breaker for FIFO within same score
        score = float(entry.score) + (entry.enqueued_at / 1_000_000_000.0)

        pipe = redis.pipeline()
        pipe.zadd(queue_key, {payload: score})
        pipe.expire(queue_key, self._ttl_s)
        pipe.setex(entry_key, self._ttl_s, payload)
        await pipe.execute()

        rank = await redis.zrevrank(queue_key, payload)
        position = int(rank) + 1 if rank is not None else 1
        logger.debug(
            "prioritization enqueue org={} customer={} score={} pos={}",
            entry.organization_id,
            entry.customer_id,
            entry.score,
            position,
        )
        return True, position

    async def dequeue_next(self, organization_id: int) -> PrioritizedCallEntry | None:
        redis = await self._get_redis()
        queue_key = self._queue_key(organization_id)
        items = await redis.zrevrange(queue_key, 0, 0)
        if not items:
            return None
        payload = items[0]
        data = json.loads(payload)
        await redis.zrem(queue_key, payload)
        await redis.delete(self._entry_key(organization_id, int(data["customer_id"])))
        return PrioritizedCallEntry.from_dict(data)

    async def remove(self, organization_id: int, customer_id: int) -> bool:
        redis = await self._get_redis()
        entry_key = self._entry_key(organization_id, customer_id)
        raw = await redis.get(entry_key)
        if not raw:
            return False
        queue_key = self._queue_key(organization_id)
        await redis.zrem(queue_key, raw)
        await redis.delete(entry_key)
        return True

    async def depth(self, organization_id: int) -> int:
        redis = await self._get_redis()
        return int(await redis.zcard(self._queue_key(organization_id)))

    async def position(self, organization_id: int, customer_id: int) -> int | None:
        redis = await self._get_redis()
        raw = await redis.get(self._entry_key(organization_id, customer_id))
        if not raw:
            return None
        rank = await redis.zrevrank(self._queue_key(organization_id), raw)
        return int(rank) + 1 if rank is not None else None

    async def list_queue(
        self,
        organization_id: int,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        items = await redis.zrevrange(self._queue_key(organization_id), 0, limit - 1)
        return [json.loads(item) for item in items]

    async def refresh_score(
        self,
        organization_id: int,
        customer_id: int,
        *,
        new_score: float,
    ) -> bool:
        redis = await self._get_redis()
        entry_key = self._entry_key(organization_id, customer_id)
        raw = await redis.get(entry_key)
        if not raw:
            return False
        data = json.loads(raw)
        queue_key = self._queue_key(organization_id)
        await redis.zrem(queue_key, raw)
        data["score"] = round(new_score, 2)
        entry = PrioritizedCallEntry.from_dict(data)
        await self.enqueue(entry)
        return True


class PrioritizationRetryQueue:
    """Time-ordered retry queue — score = unix timestamp when due."""

    def __init__(self, redis_client: aioredis.Redis | None = None, *, ttl_s: int = 86400 * 14) -> None:
        self._redis = redis_client
        self._ttl_s = ttl_s

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _retry_key(organization_id: int) -> str:
        return f"call_prioritization:retry:{organization_id}"

    async def schedule(self, schedule: RetrySchedule, entry: PrioritizedCallEntry) -> None:
        redis = await self._get_redis()
        key = self._retry_key(schedule.organization_id)
        payload = json.dumps({**entry.to_dict(), "retry": schedule.to_dict()})
        pipe = redis.pipeline()
        pipe.zadd(key, {payload: schedule.scheduled_at})
        pipe.expire(key, self._ttl_s)
        await pipe.execute()

    async def due_entries(
        self,
        organization_id: int,
        *,
        now: float | None = None,
        limit: int = 50,
    ) -> list[tuple[PrioritizedCallEntry, RetrySchedule]]:
        redis = await self._get_redis()
        key = self._retry_key(organization_id)
        cutoff = now if now is not None else time.time()
        items = await redis.zrangebyscore(key, 0, cutoff, start=0, num=limit)
        results: list[tuple[PrioritizedCallEntry, RetrySchedule]] = []
        for raw in items:
            data = json.loads(raw)
            retry_data = data.pop("retry", {})
            entry = PrioritizedCallEntry.from_dict(data)
            results.append(
                (
                    entry,
                    RetrySchedule(
                        customer_id=int(retry_data["customer_id"]),
                        organization_id=int(retry_data["organization_id"]),
                        scheduled_at=float(retry_data["scheduled_at"]),
                        attempt_number=int(retry_data["attempt_number"]),
                        reason=str(retry_data.get("reason", "")),
                        score=float(retry_data.get("score", 0)),
                        delay_s=int(retry_data.get("delay_s", 0)),
                    ),
                )
            )
            await redis.zrem(key, raw)
        return results

    async def list_pending(
        self,
        organization_id: int,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        key = self._retry_key(organization_id)
        items = await redis.zrange(key, 0, limit - 1, withscores=True)
        return [{**json.loads(raw), "scheduled_at": scheduled_at} for raw, scheduled_at in items]

    async def depth(self, organization_id: int) -> int:
        redis = await self._get_redis()
        return int(await redis.zcard(self._retry_key(organization_id)))
