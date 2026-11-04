"""Aggregate voice analytics events into business-call KPIs."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from api.db import db_client
from api.services.business_call_analytics.schema import (
    BUSINESS_CALL_KPIS,
    KPI_AVG_CALL_DURATION,
    KPI_CUSTOMER_SENTIMENT,
    KPI_ESCALATION_RATE,
    KPI_PAYMENT_PROMISES,
    KPI_REPAYMENT_CONVERSION,
    KPI_SUCCESSFUL_NEGOTIATIONS,
    ROLLUP_EVENT_TYPES,
)
from api.services.business_call_analytics.types import (
    BusinessCallMetricsSnapshot,
    KpiValue,
    TimeseriesPoint,
)
from api.services.voice_analytics.store import VoiceAnalyticsStore
from api.services.voice_analytics.types import MetricAggregate, VoiceAnalyticsEventType


def _safe_rate(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _merge_rows(rows: list[dict[str, Any]]) -> MetricAggregate:
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


class BusinessCallAggregator:
    """Roll up stored events into production business-call KPIs."""

    def __init__(
        self,
        store: VoiceAnalyticsStore | None = None,
    ) -> None:
        self._store = store or VoiceAnalyticsStore()

    async def _rollup(
        self,
        organization_id: int,
        event_type: str,
        *,
        from_ts: float,
        to_ts: float,
    ) -> MetricAggregate:
        buckets = await self._store.list_buckets(
            organization_id,
            event_type,
            granularity="day",
            from_ts=from_ts,
            to_ts=to_ts,
        )
        agg = _merge_rows(buckets)
        agg.metric = event_type
        return agg

    async def _total_calls(
        self,
        organization_id: int,
        *,
        from_ts: float,
        to_ts: float,
        rollups: dict[str, MetricAggregate],
    ) -> int:
        for event in (
            VoiceAnalyticsEventType.CALL_STARTED.value,
            VoiceAnalyticsEventType.RESPONSE_LATENCY.value,
            VoiceAnalyticsEventType.NEGOTIATION_OFFER.value,
        ):
            count = rollups.get(event, MetricAggregate(metric=event)).count
            if count > 0:
                return count
        db_stats = await db_client.get_business_call_duration_stats(
            organization_id,
            from_ts=datetime.fromtimestamp(from_ts, tz=timezone.utc),
            to_ts=datetime.fromtimestamp(to_ts, tz=timezone.utc),
        )
        return int(db_stats.get("call_count", 0))

    async def compute_snapshot(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> BusinessCallMetricsSnapshot:
        now = time.time()
        start = from_ts if from_ts is not None else now - 86400 * 7
        end = to_ts if to_ts is not None else now

        rollups: dict[str, MetricAggregate] = {}
        for event_type in ROLLUP_EVENT_TYPES:
            rollups[event_type] = await self._rollup(
                organization_id,
                event_type,
                from_ts=start,
                to_ts=end,
            )

        total_calls = await self._total_calls(
            organization_id, from_ts=start, to_ts=end, rollups=rollups
        )
        repayments = _merge_rows(
            [
                rollups[VoiceAnalyticsEventType.REPAYMENT_COLLECTED.value].to_dict(),
                rollups[VoiceAnalyticsEventType.PAYMENT_SUCCESS.value].to_dict(),
            ]
        )
        negotiations = rollups[VoiceAnalyticsEventType.NEGOTIATION_OFFER.value]
        escalations = _merge_rows(
            [
                rollups[VoiceAnalyticsEventType.ESCALATION.value].to_dict(),
                rollups[VoiceAnalyticsEventType.DEBT_ESCALATION_RISK.value].to_dict(),
            ]
        )
        promises = _merge_rows(
            [
                rollups[VoiceAnalyticsEventType.PAYMENT_COMMITMENT.value].to_dict(),
                rollups[VoiceAnalyticsEventType.INSTALLMENT_SCHEDULED.value].to_dict(),
            ]
        )
        sentiments = rollups[VoiceAnalyticsEventType.CUSTOMER_SENTIMENT.value]
        call_ended = rollups[VoiceAnalyticsEventType.CALL_ENDED.value]

        repayment_rate = _safe_rate(repayments.success_count, total_calls)
        negotiation_rate = _safe_rate(negotiations.success_count, negotiations.count)
        escalation_rate = _safe_rate(escalations.count, max(1, total_calls))

        avg_duration: float | None = None
        duration_count = call_ended.count
        if call_ended.count > 0 and call_ended.sum_value > 0:
            avg_duration = round(call_ended.sum_value / call_ended.count, 2)
        else:
            db_stats = await db_client.get_business_call_duration_stats(
                organization_id,
                from_ts=datetime.fromtimestamp(start, tz=timezone.utc),
                to_ts=datetime.fromtimestamp(end, tz=timezone.utc),
            )
            db_count = int(db_stats.get("call_count", 0))
            db_total = float(db_stats.get("total_duration_s", 0.0))
            if db_count > 0:
                avg_duration = round(db_total / db_count, 2)
                duration_count = db_count
                if total_calls == 0:
                    total_calls = db_count

        avg_sentiment = sentiments.avg_value

        kpis = {
            KPI_REPAYMENT_CONVERSION: KpiValue(
                name=KPI_REPAYMENT_CONVERSION,
                value=repayment_rate,
                unit="rate",
                count=total_calls,
                success_count=repayments.success_count,
                rate=repayment_rate,
                metadata={
                    "collected_amount": round(repayments.sum_value, 2),
                    "repayment_events": repayments.count,
                },
            ),
            KPI_SUCCESSFUL_NEGOTIATIONS: KpiValue(
                name=KPI_SUCCESSFUL_NEGOTIATIONS,
                value=negotiation_rate,
                unit="rate",
                count=negotiations.count,
                success_count=negotiations.success_count,
                rate=negotiation_rate,
            ),
            KPI_ESCALATION_RATE: KpiValue(
                name=KPI_ESCALATION_RATE,
                value=escalation_rate,
                unit="rate",
                count=total_calls,
                success_count=escalations.count,
                rate=escalation_rate,
                metadata={"escalation_events": escalations.count},
            ),
            KPI_PAYMENT_PROMISES: KpiValue(
                name=KPI_PAYMENT_PROMISES,
                value=promises.count,
                unit="count",
                count=promises.count,
                success_count=promises.success_count,
                metadata={"committed_amount": round(promises.sum_value, 2)},
            ),
            KPI_AVG_CALL_DURATION: KpiValue(
                name=KPI_AVG_CALL_DURATION,
                value=avg_duration,
                unit="seconds",
                count=duration_count,
                metadata={"total_duration_s": round(call_ended.sum_value, 2)},
            ),
            KPI_CUSTOMER_SENTIMENT: KpiValue(
                name=KPI_CUSTOMER_SENTIMENT,
                value=round(avg_sentiment, 4) if avg_sentiment is not None else None,
                unit="score",
                count=sentiments.count,
                metadata={
                    "positive": sentiments.success_count,
                    "negative": sentiments.failure_count,
                },
            ),
        }

        rates = {
            KPI_REPAYMENT_CONVERSION: repayment_rate,
            KPI_SUCCESSFUL_NEGOTIATIONS: negotiation_rate,
            KPI_ESCALATION_RATE: escalation_rate,
        }

        return BusinessCallMetricsSnapshot(
            organization_id=organization_id,
            from_ts=start,
            to_ts=end,
            generated_at=now,
            total_calls=total_calls,
            kpis=kpis,
            rates=rates,
        )

    async def kpi_timeseries(
        self,
        organization_id: int,
        kpi: str,
        *,
        granularity: str = "day",
        from_ts: float,
        to_ts: float,
    ) -> list[TimeseriesPoint]:
        if kpi == KPI_REPAYMENT_CONVERSION:
            return await self._conversion_timeseries(
                organization_id,
                numerator_types=(
                    VoiceAnalyticsEventType.REPAYMENT_COLLECTED.value,
                    VoiceAnalyticsEventType.PAYMENT_SUCCESS.value,
                ),
                denominator_type=VoiceAnalyticsEventType.CALL_STARTED.value,
                metric=kpi,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        if kpi == KPI_SUCCESSFUL_NEGOTIATIONS:
            rows = await self._store.list_buckets(
                organization_id,
                VoiceAnalyticsEventType.NEGOTIATION_OFFER.value,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            return [
                TimeseriesPoint(
                    bucket=row["bucket"],
                    metric=kpi,
                    count=int(row.get("count", 0)),
                    sum=float(row.get("sum", 0.0)),
                    success_count=int(row.get("success_count", 0)),
                    rate=_safe_rate(
                        float(row.get("success_count", 0)),
                        float(row.get("count", 0)),
                    ),
                )
                for row in rows
            ]
        if kpi == KPI_ESCALATION_RATE:
            return await self._conversion_timeseries(
                organization_id,
                numerator_types=(
                    VoiceAnalyticsEventType.ESCALATION.value,
                    VoiceAnalyticsEventType.DEBT_ESCALATION_RISK.value,
                ),
                denominator_type=VoiceAnalyticsEventType.CALL_STARTED.value,
                metric=kpi,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        if kpi == KPI_PAYMENT_PROMISES:
            rows_a = await self._store.list_buckets(
                organization_id,
                VoiceAnalyticsEventType.PAYMENT_COMMITMENT.value,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            rows_b = await self._store.list_buckets(
                organization_id,
                VoiceAnalyticsEventType.INSTALLMENT_SCHEDULED.value,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            by_bucket: dict[str, dict[str, float]] = {}
            for row in rows_a + rows_b:
                bucket = row["bucket"]
                slot = by_bucket.setdefault(bucket, {"count": 0.0, "sum": 0.0})
                slot["count"] += float(row.get("count", 0))
                slot["sum"] += float(row.get("sum", 0.0))
            return [
                TimeseriesPoint(
                    bucket=bucket,
                    metric=kpi,
                    count=int(vals["count"]),
                    sum=vals["sum"],
                )
                for bucket, vals in sorted(by_bucket.items())
            ]
        if kpi == KPI_AVG_CALL_DURATION:
            rows = await self._store.list_buckets(
                organization_id,
                VoiceAnalyticsEventType.CALL_ENDED.value,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            return [
                TimeseriesPoint(
                    bucket=row["bucket"],
                    metric=kpi,
                    count=int(row.get("count", 0)),
                    sum=float(row.get("sum", 0.0)),
                    avg=row.get("avg"),
                )
                for row in rows
            ]
        if kpi == KPI_CUSTOMER_SENTIMENT:
            rows = await self._store.list_buckets(
                organization_id,
                VoiceAnalyticsEventType.CUSTOMER_SENTIMENT.value,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            return [
                TimeseriesPoint(
                    bucket=row["bucket"],
                    metric=kpi,
                    count=int(row.get("count", 0)),
                    sum=float(row.get("sum", 0.0)),
                    avg=row.get("avg"),
                )
                for row in rows
            ]
        return []

    async def _conversion_timeseries(
        self,
        organization_id: int,
        *,
        numerator_types: tuple[str, ...],
        denominator_type: str,
        metric: str,
        granularity: str,
        from_ts: float,
        to_ts: float,
    ) -> list[TimeseriesPoint]:
        numer_by_bucket: dict[str, float] = {}
        for event_type in numerator_types:
            rows = await self._store.list_buckets(
                organization_id,
                event_type,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            for row in rows:
                numer_by_bucket[row["bucket"]] = numer_by_bucket.get(
                    row["bucket"], 0.0
                ) + float(row.get("success_count", row.get("count", 0)))

        denom_rows = await self._store.list_buckets(
            organization_id,
            denominator_type,
            granularity=granularity,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        if not denom_rows and denominator_type != VoiceAnalyticsEventType.RESPONSE_LATENCY.value:
            denom_rows = await self._store.list_buckets(
                organization_id,
                VoiceAnalyticsEventType.RESPONSE_LATENCY.value,
                granularity=granularity,
                from_ts=from_ts,
                to_ts=to_ts,
            )

        points: list[TimeseriesPoint] = []
        for row in denom_rows:
            bucket = row["bucket"]
            denom = float(row.get("count", 0))
            numer = numer_by_bucket.get(bucket, 0.0)
            points.append(
                TimeseriesPoint(
                    bucket=bucket,
                    metric=metric,
                    count=int(denom),
                    success_count=int(numer),
                    rate=_safe_rate(numer, denom),
                )
            )
        return points

    async def aggregate_and_cache(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        cache_store: Any = None,
    ) -> BusinessCallMetricsSnapshot:
        snapshot = await self.compute_snapshot(
            organization_id, from_ts=from_ts, to_ts=to_ts
        )
        if cache_store is not None:
            await cache_store.save_snapshot(snapshot)
        return snapshot
