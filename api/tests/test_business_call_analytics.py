"""Tests for AI business call analytics."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.services.business_call_analytics.aggregator import BusinessCallAggregator
from api.services.business_call_analytics.export import export_metrics_csv
from api.services.business_call_analytics.schema import (
    BUSINESS_CALL_KPIS,
    KPI_REPAYMENT_CONVERSION,
    KPI_SCHEMA,
)
from api.services.business_call_analytics.types import BusinessCallMetricsSnapshot, KpiValue
from api.services.voice_analytics.types import MetricAggregate, VoiceAnalyticsEventType


def test_kpi_schema_covers_required_metrics():
    assert KPI_REPAYMENT_CONVERSION in KPI_SCHEMA
    assert len(BUSINESS_CALL_KPIS) == 6
    for kpi in BUSINESS_CALL_KPIS:
        assert kpi in KPI_SCHEMA


def test_export_metrics_csv():
    snapshot = BusinessCallMetricsSnapshot(
        organization_id=1,
        from_ts=1000.0,
        to_ts=2000.0,
        generated_at=1500.0,
        total_calls=10,
        kpis={
            KPI_REPAYMENT_CONVERSION: KpiValue(
                name=KPI_REPAYMENT_CONVERSION,
                value=0.3,
                unit="rate",
                count=10,
                success_count=3,
                rate=0.3,
            )
        },
    )
    output, filename = export_metrics_csv(snapshot)
    body = output.getvalue()
    assert "repayment_conversion" in body
    assert filename.endswith(".csv")


@pytest.mark.asyncio
async def test_compute_snapshot_rates():
    aggregator = BusinessCallAggregator(store=AsyncMock())

    async def fake_rollup(org_id, event_type, *, from_ts, to_ts):
        data = {
            VoiceAnalyticsEventType.CALL_STARTED.value: MetricAggregate(
                metric="call_started", count=10
            ),
            VoiceAnalyticsEventType.REPAYMENT_COLLECTED.value: MetricAggregate(
                metric="repayment_collected", count=3, success_count=3, sum_value=9000.0
            ),
            VoiceAnalyticsEventType.PAYMENT_SUCCESS.value: MetricAggregate(
                metric="payment_success", count=0
            ),
            VoiceAnalyticsEventType.NEGOTIATION_OFFER.value: MetricAggregate(
                metric="negotiation_offer", count=8, success_count=5
            ),
            VoiceAnalyticsEventType.ESCALATION.value: MetricAggregate(
                metric="escalation", count=2
            ),
            VoiceAnalyticsEventType.DEBT_ESCALATION_RISK.value: MetricAggregate(
                metric="debt_escalation_risk", count=1
            ),
            VoiceAnalyticsEventType.PAYMENT_COMMITMENT.value: MetricAggregate(
                metric="payment_commitment", count=4, sum_value=12000.0
            ),
            VoiceAnalyticsEventType.INSTALLMENT_SCHEDULED.value: MetricAggregate(
                metric="installment_scheduled", count=1
            ),
            VoiceAnalyticsEventType.CUSTOMER_SENTIMENT.value: MetricAggregate(
                metric="customer_sentiment", count=6, sum_value=1.2
            ),
            VoiceAnalyticsEventType.CALL_ENDED.value: MetricAggregate(
                metric="call_ended", count=10, sum_value=1200.0
            ),
            VoiceAnalyticsEventType.RESPONSE_LATENCY.value: MetricAggregate(
                metric="response_latency", count=0
            ),
            VoiceAnalyticsEventType.CALL_OUTCOME_RECORDED.value: MetricAggregate(
                metric="call_outcome_recorded", count=0
            ),
        }
        return data.get(event_type, MetricAggregate(metric=event_type))

    aggregator._rollup = fake_rollup  # noqa: SLF001

    with patch(
        "api.services.business_call_analytics.aggregator.db_client.get_business_call_duration_stats",
        new_callable=AsyncMock,
        return_value={"call_count": 0, "total_duration_s": 0.0},
    ):
        snapshot = await aggregator.compute_snapshot(1, from_ts=1000.0, to_ts=2000.0)

    assert snapshot.total_calls == 10
    assert snapshot.kpis[KPI_REPAYMENT_CONVERSION].rate == 0.3
    assert snapshot.kpis["successful_negotiations"].rate == 0.625
    assert snapshot.kpis["payment_promises"].count == 5
    assert snapshot.kpis["avg_call_duration"].value == 120.0
    assert snapshot.kpis["customer_sentiment"].value == 0.2


@pytest.mark.asyncio
async def test_reporting_service_schema():
    from api.services.business_call_analytics.reporting import BusinessCallReportingService

    svc = BusinessCallReportingService()
    schema = svc.schema()
    assert len(schema["kpis"]) == 6
