from __future__ import annotations

import time
from typing import Any

from api.services.voice_analytics.store import VoiceAnalyticsStore
from api.services.voice_analytics.types import MetricAggregate


class VoiceAnalyticsAggregator:
    """Roll up stored events into dashboard-ready aggregates."""

    def __init__(self, store: VoiceAnalyticsStore | None = None) -> None:
        self._store = store or VoiceAnalyticsStore()

    async def aggregate_organization(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        start = from_ts if from_ts is not None else now - 86400 * 7
        end = to_ts if to_ts is not None else now
        summary = await self._store.dashboard_summary(
            organization_id,
            from_ts=start,
            to_ts=end,
        )
        return {
            "organization_id": organization_id,
            "from_ts": start,
            "to_ts": end,
            "generated_at": now,
            "metrics": summary,
        }

    async def timeseries(
        self,
        organization_id: int,
        metric: str,
        *,
        granularity: str = "hour",
        from_ts: float,
        to_ts: float,
    ) -> list[dict[str, Any]]:
        return await self._store.list_buckets(
            organization_id,
            metric,
            granularity=granularity,
            from_ts=from_ts,
            to_ts=to_ts,
        )

    @staticmethod
    def merge_aggregates(rows: list[dict[str, Any]]) -> MetricAggregate:
        total = MetricAggregate(metric="combined")
        for row in rows:
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
        return total
