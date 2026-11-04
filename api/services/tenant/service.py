"""Tenant service: members, configuration, and workflow scoping."""

from __future__ import annotations

from fastapi import HTTPException

from api.db import db_client
from api.services.control_plane.audit import USER_INVITED, log_admin_action
from api.services.tenant.access_control import assert_same_tenant
from api.services.tenant.config import load_tenant_configuration, save_tenant_configuration
from api.services.tenant.rbac import can_assign_role
from api.services.tenant.schema import (
    TenantConfigurationSchema,
    TenantMemberSchema,
)
from api.services.tenant.types import TenantContext, TenantRole


class TenantService:
    async def get_context_summary(self, ctx: TenantContext) -> dict:
        config = await load_tenant_configuration(ctx.organization_id)
        from api.constants import TENANT_ISOLATION_ENABLED

        return {
            "organization_id": ctx.organization_id,
            "user_id": ctx.user_id,
            "role": ctx.role,
            "permissions": sorted(p.value for p in ctx.permissions),
            "billing_enabled": ctx.billing_enabled,
            "isolation_enabled": TENANT_ISOLATION_ENABLED,
            "plan_id": config.billing.plan_id,
        }

    async def list_members(self, ctx: TenantContext) -> list[TenantMemberSchema]:
        ctx.require_permission("member:read")
        rows = await db_client.list_members_with_users(ctx.organization_id)
        return [
            TenantMemberSchema(
                user_id=member.user_id,
                role=TenantRole(member.role),
                email=user.email if user else None,
                created_at=member.created_at.isoformat() if member.created_at else None,
            )
            for member, user in rows
        ]

    async def add_member(
        self,
        ctx: TenantContext,
        *,
        user_id: int,
        role: TenantRole,
    ) -> TenantMemberSchema:
        ctx.require_permission("member:write")
        if not can_assign_role(ctx.role, role):
            raise HTTPException(status_code=403, detail="Cannot assign this role")
        if role == TenantRole.OWNER and ctx.role != TenantRole.OWNER:
            raise HTTPException(status_code=403, detail="Only owners can assign owner role")

        await db_client.add_user_to_organization(user_id, ctx.organization_id)
        member = await db_client.upsert_organization_member_role(
            ctx.organization_id, user_id, role
        )
        user = await db_client.get_user_by_id(user_id)
        await log_admin_action(
            organization_id=ctx.organization_id,
            action=USER_INVITED,
            resource_type="member",
            actor_user_id=ctx.user_id,
            resource_id=str(user_id),
            summary=f"User {user_id} added with role {role.value}",
        )
        return TenantMemberSchema(
            user_id=member.user_id,
            role=TenantRole(member.role),
            email=user.email if user else None,
            created_at=member.created_at.isoformat() if member.created_at else None,
        )

    async def update_member_role(
        self,
        ctx: TenantContext,
        *,
        user_id: int,
        role: TenantRole,
    ) -> TenantMemberSchema:
        ctx.require_permission("member:write")
        if not can_assign_role(ctx.role, role):
            raise HTTPException(status_code=403, detail="Cannot assign this role")
        if role == TenantRole.OWNER and ctx.role != TenantRole.OWNER:
            raise HTTPException(status_code=403, detail="Only owners can assign owner role")

        existing = await db_client.get_organization_member(ctx.organization_id, user_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Member not found")
        if existing.role == TenantRole.OWNER.value and ctx.role != TenantRole.OWNER:
            raise HTTPException(status_code=403, detail="Cannot modify owner role")

        member = await db_client.upsert_organization_member_role(
            ctx.organization_id, user_id, role
        )
        user = await db_client.get_user_by_id(user_id)
        return TenantMemberSchema(
            user_id=member.user_id,
            role=TenantRole(member.role),
            email=user.email if user else None,
            created_at=member.created_at.isoformat() if member.created_at else None,
        )

    async def get_configuration(self, ctx: TenantContext) -> TenantConfigurationSchema:
        ctx.require_permission("config:read")
        return await load_tenant_configuration(ctx.organization_id)

    async def update_configuration(
        self,
        ctx: TenantContext,
        configuration: TenantConfigurationSchema,
    ) -> TenantConfigurationSchema:
        ctx.require_permission("config:write")
        return await save_tenant_configuration(ctx.organization_id, configuration)

    def assert_workflow_access(
        self,
        ctx: TenantContext,
        workflow_organization_id: int,
    ) -> None:
        assert_same_tenant(ctx, workflow_organization_id)


def get_tenant_service() -> TenantService:
    return TenantService()
