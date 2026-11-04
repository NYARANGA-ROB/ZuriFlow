from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

from api.constants import REDIS_URL, VOICE_ANALYTICS_EVENT_TTL_S, VOICE_ANALYTICS_MAX_EVENTS_PER_ORG
from api.services.voice_analytics.types import MetricAggregate, VoiceAnalyticsEvent


def _bucket_key(ts: float, granularity: str) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    if granularity == "hour":
        return dt.strftime("%Y%m%d%H")
    if granularity == "day":
        return dt.strftime("%Y%m%d")
    return dt.strftime("%Y%m%d%H%M")


class VoiceAnalyticsStore:
    """Redis-backed event log and time-bucket aggregates."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        *,
        event_ttl_s: int = VOICE_ANALYTICS_EVENT_TTL_S,
        max_events_per_org: int = VOICE_ANALYTICS_MAX_EVENTS_PER_ORG,
    ) -> None:
        self._redis = redis_client
        self._event_ttl_s = event_ttl_s
        self._max_events = max_events_per_org

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _events_key(organization_id: int) -> str:
        return f"voice_analytics:events:{organization_id}"

    @staticmethod
    def _agg_key(organization_id: int, bucket: str, metric: str) -> str:
        return f"voice_analytics:agg:{organization_id}:{bucket}:{metric}"

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"voice_analytics:session:{session_id}"

    async def append_event(self, event: VoiceAnalyticsEvent) -> None:
        redis = await self._get_redis()
        payload = json.dumps(event.to_dict(), separators=(",", ":"))
        events_key = self._events_key(event.organization_id)

        pipe = redis.pipeline()
        pipe.lpush(events_key, payload)
        pipe.ltrim(events_key, 0, self._max_events - 1)
        pipe.expire(events_key, self._event_ttl_s)
        if event.session_id:
            pipe.setex(
                self._session_key(event.session_id),
                self._event_ttl_s,
                json.dumps(
                    {
                        "organization_id": event.organization_id,
                        "workflow_run_id": event.workflow_run_id,
                        "last_event_at": event.timestamp,
                    }
                ),
            )
        await pipe.execute()
        await self._increment_aggregates(event)

    async def _increment_aggregates(self, event: VoiceAnalyticsEvent) -> None:
        redis = await self._get_redis()
        for granularity in ("hour", "day"):
            bucket = _bucket_key(event.timestamp, granularity)
            key = self._agg_key(event.organization_id, bucket, event.event_type.value)
            pipe = redis.pipeline()
            pipe.hincrby(key, "count", 1)
            if event.value is not None:
                pipe.hincrbyfloat(key, "sum", float(event.value))
                pipe.hsetnx(key, "min", str(event.value))
                pipe.hsetnx(key, "max", str(event.value))
            if event.success is True:
                pipe.hincrby(key, "success_count", 1)
            elif event.success is False:
                pipe.hincrby(key, "failure_count", 1)
            pipe.expire(key, self._event_ttl_s)
            await pipe.execute()

            if event.value is not None:
                current_min = await redis.hget(key, "min")
                current_max = await redis.hget(key, "max")
                if current_min is not None and float(event.value) < float(current_min):
                    await redis.hset(key, "min", str(event.value))
                if current_max is not None and float(event.value) > float(current_max):
                    await redis.hset(key, "max", str(event.value))

    async def list_events(
        self,
        organization_id: int,
        *,
        event_type: str | None = None,
        limit: int = 50,
        since_ts: float | None = None,
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        raw_items = await redis.lrange(self._events_key(organization_id), 0, limit * 3)
        events: list[dict[str, Any]] = []
        for raw in raw_items:
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event_type and item.get("event_type") != event_type:
                continue
            if since_ts is not None and float(item.get("timestamp", 0)) < since_ts:
                continue
            events.append(item)
            if len(events) >= limit:
                break
        return events

    async def get_aggregate(
        self,
        organization_id: int,
        metric: str,
        *,
        bucket: str,
    ) -> MetricAggregate:
        redis = await self._get_redis()
        key = self._agg_key(organization_id, bucket, metric)
        data = await redis.hgetall(key)
        agg = MetricAggregate(metric=metric)
        if not data:
            return agg
        agg.count = int(data.get("count", 0))
        agg.sum_value = float(data.get("sum", 0.0))
        agg.min_value = float(data["min"]) if data.get("min") is not None else None
        agg.max_value = float(data["max"]) if data.get("max") is not None else None
        agg.success_count = int(data.get("success_count", 0))
        agg.failure_count = int(data.get("failure_count", 0))
        return agg

    async def list_buckets(
        self,
        organization_id: int,
        metric: str,
        *,
        granularity: str = "hour",
        from_ts: float,
        to_ts: float,
    ) -> list[dict[str, Any]]:
        step = 3600 if granularity == "hour" else 86400
        results: list[dict[str, Any]] = []
        cursor = int(from_ts)
        end = int(to_ts)
        while cursor <= end:
            bucket = _bucket_key(float(cursor), granularity)
            agg = await self.get_aggregate(organization_id, metric, bucket=bucket)
            if agg.count > 0:
                results.append({"bucket": bucket, **agg.to_dict()})
            cursor += step
        return results

    async def dashboard_summary(
        self,
        organization_id: int,
        *,
        from_ts: float,
        to_ts: float,
    ) -> dict[str, Any]:
        metrics = [
            "payment_success",
            "whatsapp_delivery",
            "escalation",
            "interruption",
            "response_latency",
            "customer_sentiment",
        ]
        summary: dict[str, Any] = {}
        for metric in metrics:
            total = MetricAggregate(metric=metric)
            buckets = await self.list_buckets(
                organization_id,
                metric,
                granularity="day",
                from_ts=from_ts,
                to_ts=to_ts,
            )
            for row in buckets:
                total.count += int(row.get("count", 0))
                total.sum_value += float(row.get("sum", 0.0))
                total.success_count += int(row.get("success_count", 0))
                total.failure_count += int(row.get("failure_count", 0))
                vmin = row.get("min")
                vmax = row.get("max")
                if vmin is not None:
                    total.min_value = (
                        float(vmin)
                        if total.min_value is None
                        else min(total.min_value, float(vmin))
                    )
                if vmax is not None:
                    total.max_value = (
                        float(vmax)
                        if total.max_value is None
                        else max(total.max_value, float(vmax))
                    )
            summary[metric] = total.to_dict()

        payments = summary.get("payment_success", {})
        escalations = summary.get("escalation", {})
        interruptions = summary.get("interruption", {})
        calls = max(1, int(summary.get("response_latency", {}).get("count", 0)))
        summary["rates"] = {
            "escalation_rate": round(
                float(escalations.get("count", 0)) / calls, 4
            ),
            "interruption_frequency": round(
                float(interruptions.get("count", 0)) / calls, 4
            ),
            "payment_success_rate": (
                round(
                    float(payments.get("success_count", 0))
                    / max(1, int(payments.get("count", 0))),
                    4,
                )
                if payments.get("count")
                else None
            ),
        }
        return summary
