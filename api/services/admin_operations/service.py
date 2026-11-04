"""Facade for admin operations dashboard APIs."""

from __future__ import annotations

from typing import Any

from api.constants import ADMIN_OPERATIONS_ENABLED
from api.services.admin_operations.aggregators.calls import CallsAggregator
from api.services.admin_operations.aggregators.campaigns import CampaignsAggregator
from api.services.admin_operations.aggregators.escalations import EscalationsAggregator
from api.services.admin_operations.aggregators.payments import PaymentsAggregator
from api.services.admin_operations.aggregators.tenant import TenantAggregator
from api.services.admin_operations.aggregators.workflows import WorkflowsAggregator
from api.services.admin_operations.capabilities import build_capabilities
from api.services.admin_operations.realtime import (
    AdminOperationsRealtimeHub,
    get_admin_operations_realtime_hub,
)
from api.services.admin_operations.reporting import export_summary_csv, export_summary_json
from api.services.admin_operations.search import AdminSearchService
from api.services.admin_operations.summary import AdminSummaryBuilder
from api.services.realtime_observability.health import HEALTH_SERVICE
from api.services.tenant.types import TenantContext


class AdminOperationsService:
    """Unified admin dashboard for AI call operations."""

    def __init__(self) -> None:
        self._summary = AdminSummaryBuilder()
        self._search = AdminSearchService()
        self._calls = CallsAggregator()
        self._payments = PaymentsAggregator()
        self._campaigns = CampaignsAggregator()
        self._escalations = EscalationsAggregator()
        self._workflows = WorkflowsAggregator()
        self._tenant = TenantAggregator()
        self._realtime = get_admin_operations_realtime_hub()

    @property
    def enabled(self) -> bool:
        return ADMIN_OPERATIONS_ENABLED

    @property
    def realtime(self) -> AdminOperationsRealtimeHub:
        return self._realtime

    def capabilities(self) -> dict[str, Any]:
        return build_capabilities()

    async def health(self) -> dict[str, Any]:
        readiness = await HEALTH_SERVICE.readiness()
        return {
            "enabled": self.enabled,
            "status": readiness.status,
            "checks": readiness.checks,
        }

    async def get_summary(
        self,
        ctx: TenantContext,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        return await self._summary.build(
            ctx, from_ts=from_ts, to_ts=to_ts, days=days
        )

    async def live_calls(self, organization_id: int) -> dict[str, Any]:
        return await self._calls.live_snapshot(organization_id)

    async def recent_runs(
        self, organization_id: int, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        return await self._calls.recent_runs(
            organization_id, limit=limit, offset=offset
        )

    async def payments_summary(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        return await self._payments.summary(
            organization_id, from_ts=from_ts, to_ts=to_ts, days=days
        )

    async def campaigns(
        self, organization_id: int, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        return await self._campaigns.list_campaigns(
            organization_id, limit=limit, offset=offset
        )

    async def campaign_detail(
        self, organization_id: int, campaign_id: int
    ) -> dict[str, Any] | None:
        return await self._campaigns.campaign_detail(organization_id, campaign_id)

    async def escalations_summary(
        self, organization_id: int, *, days: int = 7
    ) -> dict[str, Any]:
        return await self._escalations.summary(organization_id, days=days)

    async def workflow_performance(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        days: int = 7,
        limit: int = 25,
    ) -> dict[str, Any]:
        return await self._workflows.performance(
            organization_id,
            from_ts=from_ts,
            to_ts=to_ts,
            days=days,
            limit=limit,
        )

    async def tenant_analytics(
        self,
        ctx: TenantContext,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> dict[str, Any]:
        return await self._tenant.summary(ctx, from_ts=from_ts, to_ts=to_ts)

    def export_report_json(self, summary: dict[str, Any]):
        return export_summary_json(summary)

    def export_report_csv(self, summary: dict[str, Any]):
        return export_summary_csv(summary)

    @property
    def search(self) -> AdminSearchService:
        return self._search


_service: AdminOperationsService | None = None


def get_admin_operations_service() -> AdminOperationsService:
    global _service
    if _service is None:
        _service = AdminOperationsService()
    return _service
