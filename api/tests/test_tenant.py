"""Tests for multi-tenant RBAC, isolation, and membership."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.db.models import OrganizationMemberModel, OrganizationModel, UserModel
from api.services.tenant.access_control import (
    TenantAccessDenied,
    assert_same_tenant,
    resolve_tenant_context,
)
from api.services.tenant.rbac import (
    can_assign_role,
    default_role_for_new_member,
    permissions_for_role,
)
from api.services.tenant.types import Permission, TenantContext, TenantRole


class TestRBACMatrix:
    def test_owner_has_all_permissions(self):
        perms = permissions_for_role(TenantRole.OWNER)
        assert Permission.WORKFLOW_WRITE in perms
        assert Permission.BILLING_WRITE in perms
        assert Permission.MEMBER_WRITE in perms

    def test_viewer_is_read_only(self):
        perms = permissions_for_role(TenantRole.VIEWER)
        assert Permission.WORKFLOW_READ in perms
        assert Permission.WORKFLOW_WRITE not in perms
        assert Permission.BILLING_WRITE not in perms

    def test_billing_role_scope(self):
        perms = permissions_for_role(TenantRole.BILLING)
        assert Permission.BILLING_WRITE in perms
        assert Permission.WORKFLOW_WRITE not in perms

    def test_operator_can_execute_workflows(self):
        perms = permissions_for_role(TenantRole.OPERATOR)
        assert Permission.WORKFLOW_EXECUTE in perms
        assert Permission.BILLING_READ not in perms

    def test_admin_cannot_assign_owner(self):
        assert can_assign_role(TenantRole.ADMIN, TenantRole.OPERATOR)
        assert not can_assign_role(TenantRole.ADMIN, TenantRole.OWNER)

    def test_default_role_for_first_member(self):
        assert default_role_for_new_member(True) == TenantRole.OWNER
        assert default_role_for_new_member(False) == TenantRole.VIEWER


class TestTenantIsolation:
    def test_assert_same_tenant_blocks_cross_tenant(self):
        ctx = TenantContext(
            organization_id=1,
            user_id=10,
            role=TenantRole.VIEWER,
            permissions=permissions_for_role(TenantRole.VIEWER),
        )
        with pytest.raises(HTTPException) as exc:
            assert_same_tenant(ctx, 2)
        assert exc.value.status_code == 404

    def test_superuser_cross_tenant_allowed(self):
        ctx = TenantContext(
            organization_id=1,
            user_id=10,
            role=TenantRole.OWNER,
            permissions=frozenset(Permission),
            is_superuser=True,
        )
        assert_same_tenant(ctx, 99)

    def test_context_permission_check(self):
        ctx = TenantContext(
            organization_id=1,
            user_id=1,
            role=TenantRole.VIEWER,
            permissions=permissions_for_role(TenantRole.VIEWER),
        )
        with pytest.raises(TenantAccessDenied):
            ctx.require_permission(Permission.WORKFLOW_WRITE)


@pytest.fixture
async def org_a(async_session):
    org = OrganizationModel(provider_id="tenant-org-a")
    async_session.add(org)
    await async_session.flush()
    return org


@pytest.fixture
async def org_b(async_session):
    org = OrganizationModel(provider_id="tenant-org-b")
    async_session.add(org)
    await async_session.flush()
    return org


@pytest.fixture
async def user_a(async_session, org_a):
    user = UserModel(
        provider_id="tenant-user-a",
        email="a@example.com",
        selected_organization_id=org_a.id,
    )
    async_session.add(user)
    await async_session.flush()
    return user


class TestTenantMembership:
    async def test_ensure_member_assigns_owner_to_first(self, db_session, org_a, user_a):
        from api.db import db_client

        member = await db_client.ensure_organization_member(org_a.id, user_a.id)
        assert member.role == TenantRole.OWNER.value

    async def test_second_member_gets_viewer(self, db_session, org_a, user_a, async_session):
        from api.db import db_client

        await db_client.ensure_organization_member(org_a.id, user_a.id)

        user_b = UserModel(
            provider_id="tenant-user-b",
            email="b@example.com",
            selected_organization_id=org_a.id,
        )
        async_session.add(user_b)
        await async_session.flush()

        member_b = await db_client.ensure_organization_member(org_a.id, user_b.id)
        assert member_b.role == TenantRole.VIEWER.value

    async def test_resolve_context_denies_non_member(
        self, db_session, org_a, org_b, user_a, async_session
    ):
        user_a.selected_organization_id = org_b.id
        async_session.add(
            OrganizationMemberModel(
                organization_id=org_a.id,
                user_id=user_a.id,
                role=TenantRole.OWNER.value,
            )
        )
        await async_session.flush()

        with pytest.raises(TenantAccessDenied):
            await resolve_tenant_context(user_a)

    async def test_resolve_context_for_member(self, db_session, org_a, user_a):
        from api.db import db_client

        await db_client.ensure_organization_member(org_a.id, user_a.id)
        ctx = await resolve_tenant_context(user_a)
        assert ctx.organization_id == org_a.id
        assert ctx.role == TenantRole.OWNER
        assert ctx.has_permission(Permission.CONFIG_WRITE)
