from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

from api.constants import REDIS_URL
from api.services.call_routing.config import CallRoutingOrgConfig, QueueConfig
from api.services.call_routing.types import QueueEntry


class CallRoutingQueueService:
    """Redis-backed priority queues for human and specialist routing."""

    def __init__(self, redis_client: aioredis.Redis | None = None, *, ttl_s: int = 3600) -> None:
        self._redis = redis_client
        self._ttl_s = ttl_s

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _queue_key(organization_id: int, queue_name: str) -> str:
        return f"call_routing:queue:{organization_id}:{queue_name}"

    @staticmethod
    def _entry_key(session_id: str) -> str:
        return f"call_routing:entry:{session_id}"

    async def enqueue(
        self,
        entry: QueueEntry,
        *,
        org_config: CallRoutingOrgConfig,
    ) -> tuple[bool, int]:
        queue_cfg = org_config.queues.get(
            entry.queue_name.split("_")[0],
            QueueConfig(name=entry.queue_name),
        )
        redis = await self._get_redis()
        queue_key = self._queue_key(entry.organization_id, entry.queue_name)

        depth = await redis.zcard(queue_key)
        if depth >= queue_cfg.max_depth:
            logger.warning(
                "call routing queue full org={} queue={} depth={}",
                entry.organization_id,
                entry.queue_name,
                depth,
            )
            return False, 0

        score = float(entry.priority) + (time.time() / 1_000_000.0)
        payload = json.dumps(entry.to_dict())
        pipe = redis.pipeline()
        pipe.zadd(queue_key, {payload: score})
        pipe.expire(queue_key, self._ttl_s)
        pipe.setex(self._entry_key(entry.session_id), self._ttl_s, payload)
        await pipe.execute()

        position = await redis.zrevrank(queue_key, payload)
        return True, int(position or 0) + 1

    async def dequeue_next(
        self,
        organization_id: int,
        queue_name: str,
    ) -> QueueEntry | None:
        redis = await self._get_redis()
        queue_key = self._queue_key(organization_id, queue_name)
        items = await redis.zrevrange(queue_key, 0, 0)
        if not items:
            return None
        payload = items[0]
        await redis.zrem(queue_key, payload)
        data = json.loads(payload)
        await redis.delete(self._entry_key(data["session_id"]))
        return QueueEntry(
            session_id=data["session_id"],
            organization_id=data["organization_id"],
            queue_name=data["queue_name"],
            priority=data["priority"],
            intent=data["intent"],
            language=data.get("language", "mixed"),
            enqueued_at=data["enqueued_at"],
            workflow_run_id=data.get("workflow_run_id", 0),
            phone_e164=data.get("phone_e164", ""),
            metadata=data.get("metadata", {}),
        )

    async def position(self, session_id: str) -> int | None:
        redis = await self._get_redis()
        raw = await redis.get(self._entry_key(session_id))
        if not raw:
            return None
        data = json.loads(raw)
        queue_key = self._queue_key(data["organization_id"], data["queue_name"])
        rank = await redis.zrevrank(queue_key, raw)
        return int(rank) + 1 if rank is not None else None

    async def get_entry(self, session_id: str) -> QueueEntry | None:
        redis = await self._get_redis()
        raw = await redis.get(self._entry_key(session_id))
        if not raw:
            return None
        data = json.loads(raw)
        return QueueEntry(
            session_id=data["session_id"],
            organization_id=data["organization_id"],
            queue_name=data["queue_name"],
            priority=data["priority"],
            intent=data["intent"],
            language=data.get("language", "mixed"),
            enqueued_at=data["enqueued_at"],
            workflow_run_id=data.get("workflow_run_id", 0),
            phone_e164=data.get("phone_e164", ""),
            metadata=data.get("metadata", {}),
        )

    async def remove(self, session_id: str) -> bool:
        redis = await self._get_redis()
        raw = await redis.get(self._entry_key(session_id))
        if not raw:
            return False
        data = json.loads(raw)
        queue_key = self._queue_key(data["organization_id"], data["queue_name"])
        await redis.zrem(queue_key, raw)
        await redis.delete(self._entry_key(session_id))
        return True

    async def depth(self, organization_id: int, queue_name: str) -> int:
        redis = await self._get_redis()
        return int(await redis.zcard(self._queue_key(organization_id, queue_name)))

    async def list_queue(
        self,
        organization_id: int,
        queue_name: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        queue_key = self._queue_key(organization_id, queue_name)
        items = await redis.zrevrange(queue_key, 0, limit - 1)
        return [json.loads(item) for item in items]
