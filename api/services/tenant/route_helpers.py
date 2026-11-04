"""Shared FastAPI dependencies for tenant-scoped routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from api.services.tenant.access_control import get_tenant_context, require_permission
from api.services.tenant.types import Permission, TenantContext


def analytics_read_context():
    async def _ctx(
        ctx: Annotated[
            TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))
        ],
    ) -> TenantContext:
        return ctx

    return _ctx


def config_write_context():
    async def _ctx(
        ctx: Annotated[
            TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))
        ],
    ) -> TenantContext:
        return ctx

    return _ctx


AnalyticsReadContext = Annotated[TenantContext, Depends(analytics_read_context())]
BillingReadContext = Annotated[TenantContext, Depends(require_permission(Permission.BILLING_READ))]
BillingWriteContext = Annotated[TenantContext, Depends(require_permission(Permission.BILLING_WRITE))]
TenantContextDep = Annotated[TenantContext, Depends(get_tenant_context)]
