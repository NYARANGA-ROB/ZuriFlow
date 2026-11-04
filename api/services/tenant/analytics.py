"""Tenant-scoped analytics aggregation."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from api.constants import BUSINESS_CALL_ANALYTICS_ENABLED
from api.db import db_client
from api.services.tenant.access_control import assert_same_tenant
from api.services.tenant.config import load_tenant_configuration
from api.services.tenant.schema import TenantAnalyticsSummary
from api.services.tenant.types import TenantContext


class TenantAnalyticsService:
    async def get_summary(
        self,
        ctx: TenantContext,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> TenantAnalyticsSummary:
        assert_same_tenant(ctx, ctx.organization_id)
        now = time.time()
        window_from = from_ts if from_ts is not None else now - 86400 * 7
        window_to = to_ts if to_ts is not None else now

        config = await load_tenant_configuration(ctx.organization_id)
        members = await db_client.list_organization_members(ctx.organization_id)
        workflow_counts = await db_client.get_workflow_counts(ctx.organization_id)
        active_workflows = int(workflow_counts.get("active", 0) or 0)

        metrics: dict[str, Any] = {}
        total_calls = 0
        if BUSINESS_CALL_ANALYTICS_ENABLED and config.feature_flags.business_analytics:
            stats = await db_client.get_business_call_duration_stats(
                ctx.organization_id,
                from_ts=datetime.fromtimestamp(window_from, tz=timezone.utc),
                to_ts=datetime.fromtimestamp(window_to, tz=timezone.utc),
            )
            total_calls = int(stats.get("call_count", 0) or 0)
            metrics["call_duration"] = stats

        return TenantAnalyticsSummary(
            organization_id=ctx.organization_id,
            from_ts=window_from,
            to_ts=window_to,
            total_calls=total_calls,
            active_workflows=active_workflows,
            member_count=len(members),
            billing_plan=config.billing.plan_id,
            metrics=metrics,
        )


def get_tenant_analytics_service() -> TenantAnalyticsService:
    return TenantAnalyticsService()
