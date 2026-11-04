"""Unified admin dashboard summary."""

from __future__ import annotations

import time
from typing import Any

from api.constants import BUSINESS_CALL_ANALYTICS_ENABLED
from api.services.admin_operations.aggregators.calls import CallsAggregator
from api.services.admin_operations.aggregators.campaigns import CampaignsAggregator
from api.services.admin_operations.aggregators.escalations import EscalationsAggregator
from api.services.admin_operations.aggregators.payments import PaymentsAggregator
from api.services.admin_operations.aggregators.tenant import TenantAggregator
from api.services.admin_operations.aggregators.workflows import WorkflowsAggregator
from api.services.business_call_analytics.service import get_business_call_analytics_service
from api.services.tenant.types import TenantContext


class AdminSummaryBuilder:
    def __init__(self) -> None:
        self._calls = CallsAggregator()
        self._payments = PaymentsAggregator()
        self._campaigns = CampaignsAggregator()
        self._escalations = EscalationsAggregator()
        self._workflows = WorkflowsAggregator()
        self._tenant = TenantAggregator()

    async def build(
        self,
        ctx: TenantContext,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        org_id = ctx.organization_id
        now = time.time()
        end = to_ts if to_ts is not None else now
        start = from_ts if from_ts is not None else end - days * 86400

        live = await self._calls.live_snapshot(org_id)
        payments = await self._payments.summary(
            org_id, from_ts=start, to_ts=end, days=days
        )
        campaigns = await self._campaigns.list_campaigns(org_id, limit=10)
        escalations = await self._escalations.summary(org_id, days=min(days, 30))
        workflows = await self._workflows.performance(
            org_id, from_ts=start, to_ts=end, days=days, limit=10
        )
        tenant = await self._tenant.summary(ctx, from_ts=start, to_ts=end)

        business_metrics = None
        if BUSINESS_CALL_ANALYTICS_ENABLED:
            svc = get_business_call_analytics_service()
            if svc.enabled:
                snapshot = await svc.get_metrics(
                    org_id, from_ts=start, to_ts=end, use_cache=True
                )
                business_metrics = {
                    "total_calls": snapshot.total_calls,
                    "rates": dict(snapshot.rates),
                    "kpis": {
                        name: kpi.to_dict() for name, kpi in snapshot.kpis.items()
                    },
                }

        return {
            "organization_id": org_id,
            "from_ts": start,
            "to_ts": end,
            "generated_at": now,
            "live_calls": live,
            "payments": payments,
            "campaigns": campaigns,
            "escalations": escalations,
            "workflow_performance": workflows,
            "tenant": tenant,
            "business_call_analytics": business_metrics,
        }
