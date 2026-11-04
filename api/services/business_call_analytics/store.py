"""Redis cache for pre-aggregated business call analytics snapshots."""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

from api.constants import BUSINESS_CALL_ANALYTICS_SNAPSHOT_TTL_S, REDIS_URL
from api.services.business_call_analytics.types import BusinessCallMetricsSnapshot, KpiValue


class BusinessCallAnalyticsStore:
    """Persist and retrieve rolled-up KPI snapshots."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        *,
        snapshot_ttl_s: int = BUSINESS_CALL_ANALYTICS_SNAPSHOT_TTL_S,
    ) -> None:
        self._redis = redis_client
        self._snapshot_ttl_s = snapshot_ttl_s

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _snapshot_key(organization_id: int, period_key: str) -> str:
        return f"business_call_analytics:snapshot:{organization_id}:{period_key}"

    @staticmethod
    def _latest_key(organization_id: int) -> str:
        return f"business_call_analytics:latest:{organization_id}"

    @staticmethod
    def period_key(from_ts: float, to_ts: float) -> str:
        return f"{int(from_ts)}_{int(to_ts)}"

    async def save_snapshot(self, snapshot: BusinessCallMetricsSnapshot) -> None:
        redis = await self._get_redis()
        period = self.period_key(snapshot.from_ts, snapshot.to_ts)
        payload = json.dumps(snapshot.to_dict(), separators=(",", ":"))
        pipe = redis.pipeline()
        pipe.setex(
            self._snapshot_key(snapshot.organization_id, period),
            self._snapshot_ttl_s,
            payload,
        )
        pipe.setex(
            self._latest_key(snapshot.organization_id),
            self._snapshot_ttl_s,
            payload,
        )
        await pipe.execute()

    async def get_snapshot(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> BusinessCallMetricsSnapshot | None:
        redis = await self._get_redis()
        if from_ts is not None and to_ts is not None:
            key = self._snapshot_key(
                organization_id, self.period_key(from_ts, to_ts)
            )
        else:
            key = self._latest_key(organization_id)
        raw = await redis.get(key)
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        kpis = {
            name: KpiValue(
                name=name,
                value=item.get("value"),
                unit=item.get("unit", ""),
                count=int(item.get("count", 0)),
                success_count=int(item.get("success_count", 0)),
                rate=item.get("rate"),
                metadata=dict(item.get("metadata") or {}),
            )
            for name, item in (data.get("kpis") or {}).items()
        }
        return BusinessCallMetricsSnapshot(
            organization_id=int(data["organization_id"]),
            from_ts=float(data["from_ts"]),
            to_ts=float(data["to_ts"]),
            generated_at=float(data.get("generated_at", time.time())),
            total_calls=int(data.get("total_calls", 0)),
            kpis=kpis,
            rates=dict(data.get("rates") or {}),
        )

    async def list_cached_periods(
        self, organization_id: int, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        pattern = f"business_call_analytics:snapshot:{organization_id}:*"
        keys: list[str] = []
        async for key in redis.scan_iter(match=pattern, count=50):
            keys.append(key)
            if len(keys) >= limit:
                break
        periods: list[dict[str, Any]] = []
        for key in keys:
            period = key.rsplit(":", 1)[-1]
            if "_" in period:
                start_s, end_s = period.split("_", 1)
                periods.append(
                    {
                        "period_key": period,
                        "from_ts": float(start_s),
                        "to_ts": float(end_s),
                    }
                )
        return sorted(periods, key=lambda p: p["to_ts"], reverse=True)
