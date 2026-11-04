"""Retry queues for failed calls and interrupted workflows."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from api.constants import REDIS_URL
from api.services.call_reliability.config import CallReliabilityConfig, DEFAULT_CALL_RELIABILITY_CONFIG
from api.services.call_reliability.types import RecoveryKind, RetryJob


class CallRetryQueue:
    """Time-ordered Redis ZSET for deferred call and workflow recovery jobs."""

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
    def _queue_key(organization_id: int) -> str:
        return f"call_reliability:retry:{organization_id}"

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"call_reliability:retry_job:{job_id}"

    def _delay_for_attempt(self, attempt: int) -> float:
        return self._config.retry_base_delay_s * (2 ** max(0, attempt - 1))

    async def schedule(
        self,
        *,
        organization_id: int,
        kind: RecoveryKind,
        reason: str,
        workflow_run_id: int = 0,
        session_id: str = "",
        attempt: int = 1,
        payload: dict[str, Any] | None = None,
        delay_s: float | None = None,
    ) -> RetryJob | None:
        if attempt > self._config.max_retries:
            return None

        job = RetryJob(
            job_id=str(uuid.uuid4()),
            organization_id=organization_id,
            kind=kind,
            workflow_run_id=workflow_run_id,
            session_id=session_id,
            attempt=attempt,
            max_attempts=self._config.max_retries,
            scheduled_at=time.time() + (delay_s if delay_s is not None else self._delay_for_attempt(attempt)),
            reason=reason,
            payload=dict(payload or {}),
        )

        redis = await self._get_redis()
        raw = json.dumps(job.to_dict(), separators=(",", ":"))
        pipe = redis.pipeline()
        pipe.zadd(self._queue_key(organization_id), {raw: job.scheduled_at})
        pipe.setex(self._job_key(job.job_id), self._config.event_ttl_s, raw)
        pipe.expire(self._queue_key(organization_id), self._config.event_ttl_s)
        await pipe.execute()
        return job

    async def claim_due(
        self,
        organization_id: int,
        *,
        limit: int = 25,
        now: float | None = None,
    ) -> list[RetryJob]:
        redis = await self._get_redis()
        cutoff = now if now is not None else time.time()
        queue_key = self._queue_key(organization_id)
        jobs: list[RetryJob] = []

        # Atomic pop: only one worker can claim each job.
        lua = """
        local key = KEYS[1]
        local cutoff = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        local items = redis.call('ZRANGEBYSCORE', key, 0, cutoff, 'LIMIT', 0, limit)
        local claimed = {}
        for _, raw in ipairs(items) do
            if redis.call('ZREM', key, raw) == 1 then
                table.insert(claimed, raw)
            end
        end
        return claimed
        """
        try:
            raw_items = await redis.eval(lua, 1, queue_key, cutoff, limit)
        except Exception:
            raw_items = await redis.zrangebyscore(
                queue_key, 0, cutoff, start=0, num=limit
            )
            for raw in raw_items:
                await redis.zrem(queue_key, raw)

        for raw in raw_items or []:
            try:
                jobs.append(RetryJob.from_dict(json.loads(raw)))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return jobs

    async def list_pending(
        self,
        organization_id: int,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        items = await redis.zrange(
            self._queue_key(organization_id), 0, limit - 1, withscores=True
        )
        result: list[dict[str, Any]] = []
        for raw, score in items:
            try:
                data = json.loads(raw)
                data["scheduled_at"] = float(score)
                result.append(data)
            except json.JSONDecodeError:
                continue
        return result

    async def depth(self, organization_id: int) -> int:
        redis = await self._get_redis()
        return int(await redis.zcard(self._queue_key(organization_id)))


_queue: CallRetryQueue | None = None


def get_call_retry_queue() -> CallRetryQueue:
    global _queue
    if _queue is None:
        _queue = CallRetryQueue()
    return _queue
