"""Multi-tenant management API: context, members, config, analytics, billing."""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query

from api.constants import TENANT_ISOLATION_ENABLED
from api.services.tenant.access_control import get_tenant_context, require_permission
from api.services.tenant.analytics import get_tenant_analytics_service
from api.services.tenant.billing import get_tenant_billing_service
from api.services.tenant.rbac import permissions_for_role
from api.services.tenant.schema import (
    AddMemberRequest,
    RolePermissionsResponse,
    TenantAnalyticsSummary,
    TenantBillingSnapshot,
    TenantConfigUpdateRequest,
    TenantConfigurationSchema,
    TenantContextResponse,
    TenantMemberSchema,
    UpdateMemberRoleRequest,
)
from api.services.tenant.service import get_tenant_service
from api.services.tenant.types import Permission, TenantContext, TenantRole

router = APIRouter(prefix="/tenant", tags=["tenant"])


@router.get("/context", response_model=TenantContextResponse)
async def get_context(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContextResponse:
    return TenantContextResponse(
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        role=ctx.role,
        permissions=sorted(p.value for p in ctx.permissions),
        billing_enabled=ctx.billing_enabled,
        isolation_enabled=TENANT_ISOLATION_ENABLED,
    )


@router.get("/members", response_model=List[TenantMemberSchema])
async def list_members(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.MEMBER_READ))],
) -> List[TenantMemberSchema]:
    return await get_tenant_service().list_members(ctx)


@router.post("/members", response_model=TenantMemberSchema)
async def add_member(
    body: AddMemberRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.MEMBER_WRITE))],
) -> TenantMemberSchema:
    return await get_tenant_service().add_member(
        ctx, user_id=body.user_id, role=body.role
    )


@router.patch("/members/{user_id}/role", response_model=TenantMemberSchema)
async def update_member_role(
    user_id: int,
    body: UpdateMemberRoleRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.MEMBER_WRITE))],
) -> TenantMemberSchema:
    return await get_tenant_service().update_member_role(
        ctx, user_id=user_id, role=body.role
    )


@router.get("/config", response_model=TenantConfigurationSchema)
async def get_tenant_config(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
) -> TenantConfigurationSchema:
    return await get_tenant_service().get_configuration(ctx)


@router.put("/config", response_model=TenantConfigurationSchema)
async def update_tenant_config(
    body: TenantConfigUpdateRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
) -> TenantConfigurationSchema:
    return await get_tenant_service().update_configuration(ctx, body.configuration)


@router.get("/branding")
async def get_branding(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    config = await get_tenant_service().get_configuration(ctx)
    return config.branding.model_dump()


@router.put("/branding")
async def update_branding(
    body: dict,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    from api.services.tenant.schema import TenantBrandingSettings

    config = await get_tenant_service().get_configuration(ctx)
    config.branding = TenantBrandingSettings.model_validate(
        {**config.branding.model_dump(), **body}
    )
    saved = await get_tenant_service().update_configuration(ctx, config)
    return saved.branding.model_dump()


@router.get("/product-analytics")
async def product_funnel(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
):
    from api.services.product_analytics import funnel

    return await funnel(ctx.organization_id)


@router.get("/enterprise")
async def enterprise_features(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    config = await get_tenant_service().get_configuration(ctx)
    sla = {}
    try:
        from api.services.realtime_observability.slo import evaluate_slos

        sla = evaluate_slos()
    except Exception:
        sla = {}
    return {
        "enterprise": config.enterprise.model_dump(),
        "branding": config.branding.model_dump(),
        "rbac_roles": [r.value for r in TenantRole],
        "audit_logs": True,
        "api_access": config.enterprise.api_access,
        "webhooks": config.enterprise.webhooks,
        "sla": sla,
        "note": "SSO uses OIDC/SAML issuer settings; identity federation is configured by operators.",
    }


@router.get("/analytics/summary", response_model=TenantAnalyticsSummary)
async def tenant_analytics_summary(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
    from_ts: Optional[float] = Query(default=None),
    to_ts: Optional[float] = Query(default=None),
) -> TenantAnalyticsSummary:
    return await get_tenant_analytics_service().get_summary(
        ctx, from_ts=from_ts, to_ts=to_ts
    )


@router.get("/billing/snapshot", response_model=TenantBillingSnapshot)
async def tenant_billing_snapshot(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.BILLING_READ))],
) -> TenantBillingSnapshot:
    return await get_tenant_billing_service().get_snapshot(ctx)


@router.get("/rbac/roles/{role}", response_model=RolePermissionsResponse)
async def role_permissions(role: TenantRole) -> RolePermissionsResponse:
    return RolePermissionsResponse(
        role=role,
        permissions=sorted(permissions_for_role(role), key=lambda p: p.value),
    )
