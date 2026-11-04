"""Tenant billing snapshot helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from api.db import db_client
from api.services.tenant.access_control import assert_same_tenant
from api.services.tenant.config import load_tenant_configuration
from api.services.tenant.schema import TenantBillingSnapshot
from api.services.tenant.types import TenantContext


class TenantBillingService:
    async def get_snapshot(self, ctx: TenantContext) -> TenantBillingSnapshot:
        ctx.require_permission("billing:read")
        assert_same_tenant(ctx, ctx.organization_id)

        config = await load_tenant_configuration(ctx.organization_id)
        org = await db_client.get_organization_by_id(ctx.organization_id)
        price = None
        if org and org.price_per_second_usd is not None:
            price = org.price_per_second_usd
        elif config.billing.price_per_second_usd is not None:
            price = config.billing.price_per_second_usd

        usage = await db_client.get_or_create_current_cycle(ctx.organization_id)
        period_start = None
        period_end = None
        used_tokens = None
        total_duration = None
        if usage:
            period_start = _iso(usage.period_start)
            period_end = _iso(usage.period_end)
            used_tokens = float(usage.used_dograh_tokens or 0)
            total_duration = int(usage.total_duration_seconds or 0)

        return TenantBillingSnapshot(
            organization_id=ctx.organization_id,
            billing_enabled=config.billing.mps_billing_enabled and ctx.billing_enabled,
            plan_id=config.billing.plan_id,
            price_per_second_usd=price,
            period_start=period_start,
            period_end=period_end,
            used_dograh_tokens=used_tokens,
            total_duration_seconds=total_duration,
        )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def get_tenant_billing_service() -> TenantBillingService:
    return TenantBillingService()
