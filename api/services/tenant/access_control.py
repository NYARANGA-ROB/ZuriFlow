"""Access control helpers and FastAPI dependencies for tenant isolation."""

from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from api.constants import TENANT_ISOLATION_ENABLED
from api.db import db_client
from api.db.models import UserModel
from api.services.auth.depends import get_user_with_selected_organization
from api.services.tenant.config import load_tenant_configuration
from api.services.tenant.rbac import permissions_for_role
from api.services.tenant.types import Permission, TenantContext, TenantRole


class TenantAccessDenied(HTTPException):
    def __init__(
        self,
        detail: str,
        *,
        organization_id: int | None = None,
        permission: str | None = None,
    ) -> None:
        super().__init__(status_code=HTTP_403_FORBIDDEN, detail=detail)
        self.organization_id = organization_id
        self.permission = permission


class TenantIsolationViolation(HTTPException):
    def __init__(self, detail: str = "Cross-tenant access denied") -> None:
        super().__init__(status_code=HTTP_403_FORBIDDEN, detail=detail)


async def resolve_tenant_context(
    user: UserModel,
    *,
    header_organization_id: int | None = None,
) -> TenantContext:
    organization_id = user.selected_organization_id
    if organization_id is None:
        raise HTTPException(status_code=400, detail="No organization selected")

    if header_organization_id is not None and header_organization_id != organization_id:
        raise TenantIsolationViolation(
            "X-Organization-Id does not match the authenticated organization context"
        )

    if user.is_superuser:
        config = await load_tenant_configuration(organization_id)
        return TenantContext(
            organization_id=organization_id,
            user_id=user.id,
            role=TenantRole.OWNER,
            permissions=frozenset(Permission),
            is_superuser=True,
            billing_enabled=config.billing.mps_billing_enabled,
        )

    member = await db_client.get_organization_member(organization_id, user.id)
    if member is None:
        if TENANT_ISOLATION_ENABLED:
            raise TenantAccessDenied(
                "User is not a member of this organization",
                organization_id=organization_id,
            )
        role = TenantRole.VIEWER
    else:
        try:
            role = TenantRole(member.role)
        except ValueError:
            role = TenantRole.VIEWER

    config = await load_tenant_configuration(organization_id)
    return TenantContext(
        organization_id=organization_id,
        user_id=user.id,
        role=role,
        permissions=permissions_for_role(role),
        is_superuser=False,
        billing_enabled=config.billing.mps_billing_enabled,
    )


async def get_tenant_context(
    request: Request,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
) -> TenantContext:
    header_org = _parse_header_org(request)
    ctx = await resolve_tenant_context(user, header_organization_id=header_org)
    request.state.tenant_context = ctx
    request.state.organization_id = ctx.organization_id
    return ctx


def require_permission(*required: Permission | str) -> Callable:
    """FastAPI dependency factory enforcing one or more permissions."""

    async def _check(
        ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    ) -> TenantContext:
        for perm in required:
            ctx.require_permission(perm)
        return ctx

    return _check


def assert_same_tenant(
    ctx: TenantContext,
    resource_organization_id: int,
    *,
    hide_existence: bool = True,
) -> None:
    """Ensure a resource belongs to the request tenant."""
    if resource_organization_id != ctx.organization_id and not ctx.is_superuser:
        if hide_existence:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Not found")
        raise TenantIsolationViolation()


def scoped_organization_id(ctx: TenantContext, requested_org_id: int | None) -> int:
    """Resolve org id for list/query endpoints; rejects cross-tenant reads."""
    if requested_org_id is None:
        return ctx.organization_id
    if requested_org_id != ctx.organization_id and not ctx.is_superuser:
        raise TenantIsolationViolation()
    return requested_org_id


def _parse_header_org(request: Request) -> int | None:
    raw = request.headers.get("X-Organization-Id")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Organization-Id header")
