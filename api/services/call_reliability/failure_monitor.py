"""Failure monitoring and alerting counters."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from api.constants import REDIS_URL
from api.services.call_reliability.config import CallReliabilityConfig, DEFAULT_CALL_RELIABILITY_CONFIG
from api.services.call_reliability.types import FailureRecord, FailureSeverity


class FailureMonitor:
    """Track production failures for dashboards and alerting."""

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
    def _org_counter_key(organization_id: int, day: str) -> str:
        return f"call_reliability:failures:{organization_id}:{day}"

    @staticmethod
    def _recent_key(organization_id: int) -> str:
        return f"call_reliability:failures:recent:{organization_id}"

    async def record(
        self,
        *,
        organization_id: int,
        category: str,
        message: str,
        severity: FailureSeverity = FailureSeverity.MEDIUM,
        session_id: str = "",
        workflow_run_id: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> FailureRecord:
        record = FailureRecord(
            failure_id=str(uuid.uuid4()),
            organization_id=organization_id,
            category=category,
            severity=severity,
            message=message,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            timestamp=time.time(),
            metadata=dict(metadata or {}),
        )
        try:
            redis = await self._get_redis()
            day = time.strftime("%Y%m%d")
            counter_key = self._org_counter_key(organization_id, day)
            pipe = redis.pipeline()
            pipe.hincrby(counter_key, category, 1)
            pipe.hincrby(counter_key, f"severity:{severity.value}", 1)
            pipe.expire(counter_key, self._config.event_ttl_s)
            pipe.lpush(self._recent_key(organization_id), json.dumps(record.to_dict()))
            pipe.ltrim(self._recent_key(organization_id), 0, 199)
            pipe.expire(self._recent_key(organization_id), self._config.event_ttl_s)
            await pipe.execute()
        except Exception:
            pass
        return record

    async def summary(
        self,
        organization_id: int,
        *,
        days: int = 7,
    ) -> dict[str, Any]:
        redis = await self._get_redis()
        totals: dict[str, int] = {}
        for offset in range(days):
            day = time.strftime("%Y%m%d", time.gmtime(time.time() - offset * 86400))
            data = await redis.hgetall(self._org_counter_key(organization_id, day))
            for key, val in data.items():
                totals[key] = totals.get(key, 0) + int(val)

        recent_raw = await redis.lrange(self._recent_key(organization_id), 0, 19)
        recent: list[dict[str, Any]] = []
        for raw in recent_raw:
            try:
                recent.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

        return {
            "organization_id": organization_id,
            "days": days,
            "totals": totals,
            "recent_failures": recent,
        }


_monitor: FailureMonitor | None = None


def get_failure_monitor() -> FailureMonitor:
    global _monitor
    if _monitor is None:
        _monitor = FailureMonitor()
    return _monitor
