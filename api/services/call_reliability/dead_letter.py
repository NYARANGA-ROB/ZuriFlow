"""Dead-letter queue for exhausted retries."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from api.constants import REDIS_URL
from api.services.call_reliability.config import CallReliabilityConfig, DEFAULT_CALL_RELIABILITY_CONFIG
from api.services.call_reliability.types import ReliabilityEvent, RetryJob


class DeadLetterQueue:
    """Store permanently failed jobs and events for manual inspection."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        *,
        config: CallReliabilityConfig | None = None,
    ) -> None:
        self._redis = redis_client
        self._config = config or DEFAULT_CALL_RELIABILITY_CONFIG

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _org_key(organization_id: int) -> str:
        return f"call_reliability:dlq:{organization_id}"

    async def enqueue_job(
        self,
        job: RetryJob,
        *,
        error: str = "",
    ) -> str:
        entry_id = str(uuid.uuid4())
        payload = {
            "dlq_id": entry_id,
            "enqueued_at": time.time(),
            "error": error,
            "job": job.to_dict(),
        }
        redis = await self._get_redis()
        raw = json.dumps(payload, separators=(",", ":"))
        pipe = redis.pipeline()
        pipe.lpush(self._org_key(job.organization_id), raw)
        pipe.ltrim(self._org_key(job.organization_id), 0, 999)
        pipe.expire(self._org_key(job.organization_id), self._config.dlq_ttl_s)
        await pipe.execute()
        return entry_id

    async def enqueue_event(
        self,
        event: ReliabilityEvent,
        *,
        error: str = "",
    ) -> str:
        entry_id = str(uuid.uuid4())
        payload = {
            "dlq_id": entry_id,
            "enqueued_at": time.time(),
            "error": error,
            "event": event.to_dict(),
        }
        redis = await self._get_redis()
        raw = json.dumps(payload, separators=(",", ":"))
        pipe = redis.pipeline()
        pipe.lpush(self._org_key(event.organization_id), raw)
        pipe.ltrim(self._org_key(event.organization_id), 0, 999)
        pipe.expire(self._org_key(event.organization_id), self._config.dlq_ttl_s)
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


_dlq: DeadLetterQueue | None = None


def get_dead_letter_queue() -> DeadLetterQueue:
    global _dlq
    if _dlq is None:
        _dlq = DeadLetterQueue()
    return _dlq
