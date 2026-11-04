"""Reporting service for AI business call analytics."""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

from api.services.business_call_analytics.aggregator import BusinessCallAggregator
from api.services.business_call_analytics.schema import BUSINESS_CALL_KPIS, KPI_SCHEMA
from api.services.business_call_analytics.store import BusinessCallAnalyticsStore
from api.services.business_call_analytics.types import BusinessCallReport
from api.services.voice_analytics.store import VoiceAnalyticsStore


class BusinessCallReportingService:
    """Build dashboard and executive reports from aggregated KPIs."""

    def __init__(
        self,
        aggregator: BusinessCallAggregator | None = None,
        cache: BusinessCallAnalyticsStore | None = None,
        event_store: VoiceAnalyticsStore | None = None,
    ) -> None:
        self._aggregator = aggregator or BusinessCallAggregator()
        self._cache = cache or BusinessCallAnalyticsStore()
        self._events = event_store or VoiceAnalyticsStore()

    async def metrics(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        use_cache: bool = True,
    ):
        if use_cache and from_ts is not None and to_ts is not None:
            cached = await self._cache.get_snapshot(
                organization_id, from_ts=from_ts, to_ts=to_ts
            )
            if cached is not None:
                return cached
        snapshot = await self._aggregator.compute_snapshot(
            organization_id, from_ts=from_ts, to_ts=to_ts
        )
        await self._cache.save_snapshot(snapshot)
        return snapshot

    async def build_report(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> BusinessCallReport:
        now = time.time()
        start = from_ts if from_ts is not None else now - 86400 * 7
        end = to_ts if to_ts is not None else now

        summary = await self.metrics(organization_id, from_ts=start, to_ts=end)

        by_language = await self._language_breakdown(
            organization_id, from_ts=start, to_ts=end
        )
        by_day = await self._daily_breakdown(organization_id, from_ts=start, to_ts=end)
        top_events = await self._top_events(organization_id, from_ts=start, to_ts=end)

        return BusinessCallReport(
            organization_id=organization_id,
            from_ts=start,
            to_ts=end,
            generated_at=now,
            summary=summary,
            by_language=by_language,
            by_day=by_day,
            top_events=top_events,
        )

    async def _language_breakdown(
        self,
        organization_id: int,
        *,
        from_ts: float,
        to_ts: float,
    ) -> dict[str, dict[str, Any]]:
        events = await self._events.list_events(
            organization_id, limit=500, since_ts=from_ts
        )
        breakdown: dict[str, Counter[str]] = {}
        sentiment_sums: dict[str, list[float]] = {}

        for event in events:
            if float(event.get("timestamp", 0)) > to_ts:
                continue
            lang = str(event.get("language") or "mixed")
            event_type = str(event.get("event_type", ""))
            breakdown.setdefault(lang, Counter())[event_type] += 1
            if event_type == "customer_sentiment" and event.get("value") is not None:
                sentiment_sums.setdefault(lang, []).append(float(event["value"]))

        result: dict[str, dict[str, Any]] = {}
        for lang, counter in breakdown.items():
            scores = sentiment_sums.get(lang, [])
            result[lang] = {
                "event_counts": dict(counter),
                "total_events": sum(counter.values()),
                "avg_sentiment": (
                    round(sum(scores) / len(scores), 4) if scores else None
                ),
            }
        return result

    async def _daily_breakdown(
        self,
        organization_id: int,
        *,
        from_ts: float,
        to_ts: float,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for kpi in BUSINESS_CALL_KPIS:
            points = await self._aggregator.kpi_timeseries(
                organization_id,
                kpi,
                granularity="day",
                from_ts=from_ts,
                to_ts=to_ts,
            )
            for point in points:
                rows.append(point.to_dict())
        return rows

    async def _top_events(
        self,
        organization_id: int,
        *,
        from_ts: float,
        to_ts: float,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        events = await self._events.list_events(
            organization_id, limit=1000, since_ts=from_ts
        )
        counter: Counter[str] = Counter()
        for event in events:
            if float(event.get("timestamp", 0)) > to_ts:
                continue
            counter[str(event.get("event_type", "unknown"))] += 1
        return [
            {"event_type": event_type, "count": count}
            for event_type, count in counter.most_common(limit)
        ]

    def schema(self) -> dict[str, Any]:
        return {
            "kpis": [
                {"id": kpi, **KPI_SCHEMA[kpi]}
                for kpi in BUSINESS_CALL_KPIS
            ],
        }
