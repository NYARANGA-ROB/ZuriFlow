"""Tenant analytics delegation for admin dashboard."""

from __future__ import annotations

from typing import Any

from api.services.tenant.analytics import get_tenant_analytics_service
from api.services.tenant.types import TenantContext


class TenantAggregator:
    async def summary(
        self,
        ctx: TenantContext,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> dict[str, Any]:
        summary = await get_tenant_analytics_service().get_summary(
            ctx, from_ts=from_ts, to_ts=to_ts
        )
        return summary.model_dump()
