"""Facade for AI business call analytics."""

from __future__ import annotations

from typing import Any

from api.constants import BUSINESS_CALL_ANALYTICS_ENABLED
from api.services.business_call_analytics.aggregator import BusinessCallAggregator
from api.services.business_call_analytics.export import (
    export_metrics_csv,
    export_metrics_json,
    export_report_csv,
    export_report_json,
)
from api.services.business_call_analytics.reporting import BusinessCallReportingService
from api.services.business_call_analytics.store import BusinessCallAnalyticsStore


class BusinessCallAnalyticsService:
    """Production analytics for AI business voice calls."""

    def __init__(self) -> None:
        self._aggregator = BusinessCallAggregator()
        self._cache = BusinessCallAnalyticsStore()
        self._reporting = BusinessCallReportingService(
            aggregator=self._aggregator,
            cache=self._cache,
        )

    @property
    def enabled(self) -> bool:
        return BUSINESS_CALL_ANALYTICS_ENABLED

    async def get_metrics(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        use_cache: bool = True,
    ):
        return await self._reporting.metrics(
            organization_id,
            from_ts=from_ts,
            to_ts=to_ts,
            use_cache=use_cache,
        )

    async def get_kpi(
        self,
        organization_id: int,
        kpi: str,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ):
        snapshot = await self.get_metrics(
            organization_id, from_ts=from_ts, to_ts=to_ts
        )
        if kpi not in snapshot.kpis:
            raise KeyError(f"unknown kpi: {kpi}")
        return snapshot.kpis[kpi]

    async def get_timeseries(
        self,
        organization_id: int,
        kpi: str,
        *,
        granularity: str = "day",
        from_ts: float,
        to_ts: float,
    ):
        return await self._aggregator.kpi_timeseries(
            organization_id,
            kpi,
            granularity=granularity,
            from_ts=from_ts,
            to_ts=to_ts,
        )

    async def get_report(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ):
        return await self._reporting.build_report(
            organization_id, from_ts=from_ts, to_ts=to_ts
        )

    async def trigger_aggregate(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ):
        return await self._aggregator.aggregate_and_cache(
            organization_id,
            from_ts=from_ts,
            to_ts=to_ts,
            cache_store=self._cache,
        )

    def export_metrics_csv(self, snapshot) -> tuple[Any, str]:
        return export_metrics_csv(snapshot)

    def export_report_csv(self, report) -> tuple[Any, str]:
        return export_report_csv(report)

    def export_metrics_json(self, snapshot) -> dict[str, Any]:
        return export_metrics_json(snapshot)

    def export_report_json(self, report) -> dict[str, Any]:
        return export_report_json(report)

    def schema(self) -> dict[str, Any]:
        return self._reporting.schema()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "kpis": list(self.schema()["kpis"]),
        }


_service: BusinessCallAnalyticsService | None = None


def get_business_call_analytics_service() -> BusinessCallAnalyticsService:
    global _service
    if _service is None:
        _service = BusinessCallAnalyticsService()
    return _service
