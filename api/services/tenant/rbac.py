"""Role-based access control matrix for multi-tenant organizations."""

from __future__ import annotations

from typing import FrozenSet

from api.services.tenant.types import Permission, TenantRole

_READ_SURFACE = frozenset(
    {
        Permission.WORKFLOW_READ,
        Permission.CAMPAIGN_READ,
        Permission.ANALYTICS_READ,
        Permission.CONFIG_READ,
        Permission.MEMBER_READ,
        Permission.TOOL_READ,
    }
)

_PII_SURFACE = frozenset(
    {
        Permission.CONVERSATION_PII_READ,
        Permission.RECORDING_READ,
        Permission.TRANSCRIPT_READ,
    }
)

_ROLE_PERMISSIONS: dict[TenantRole, FrozenSet[Permission]] = {
    TenantRole.OWNER: frozenset(Permission),
    TenantRole.ADMIN: frozenset(
        p for p in Permission if p not in {Permission.TENANT_ADMIN}
    ),
    TenantRole.OPERATOR: frozenset(
        {
            Permission.WORKFLOW_READ,
            Permission.WORKFLOW_WRITE,
            Permission.WORKFLOW_EXECUTE,
            Permission.CAMPAIGN_READ,
            Permission.CAMPAIGN_WRITE,
            Permission.ANALYTICS_READ,
            Permission.CONVERSATION_PII_READ,
            Permission.RECORDING_READ,
            Permission.TRANSCRIPT_READ,
            Permission.CONFIG_READ,
            Permission.TOOL_READ,
            Permission.TOOL_INVOKE,
        }
    ),
    TenantRole.OPERATIONS_MANAGER: frozenset(
        {
            Permission.WORKFLOW_READ,
            Permission.WORKFLOW_WRITE,
            Permission.WORKFLOW_EXECUTE,
            Permission.CAMPAIGN_READ,
            Permission.CAMPAIGN_WRITE,
            Permission.ANALYTICS_READ,
            Permission.CONVERSATION_PII_READ,
            Permission.RECORDING_READ,
            Permission.TRANSCRIPT_READ,
            Permission.CONFIG_READ,
            Permission.MEMBER_READ,
            Permission.TOOL_READ,
            Permission.TOOL_INVOKE,
            Permission.AUDIT_READ,
        }
    ),
    TenantRole.AGENT_MANAGER: frozenset(
        {
            Permission.WORKFLOW_READ,
            Permission.WORKFLOW_WRITE,
            Permission.WORKFLOW_EXECUTE,
            Permission.CAMPAIGN_READ,
            Permission.ANALYTICS_READ,
            Permission.CONVERSATION_PII_READ,
            Permission.RECORDING_READ,
            Permission.TRANSCRIPT_READ,
            Permission.TOOL_READ,
            Permission.TOOL_INVOKE,
            Permission.MEMBER_READ,
        }
    ),
    TenantRole.ANALYST: frozenset(
        {
            Permission.WORKFLOW_READ,
            Permission.CAMPAIGN_READ,
            Permission.ANALYTICS_READ,
            Permission.TOOL_READ,
        }
    ),
    TenantRole.VIEWER: _READ_SURFACE,
    TenantRole.READ_ONLY: _READ_SURFACE,
    TenantRole.BILLING: frozenset(
        {
            Permission.BILLING_READ,
            Permission.BILLING_WRITE,
            Permission.ANALYTICS_READ,
            Permission.PAYMENT_ANALYTICS_READ,
        }
    ),
    TenantRole.FINANCE: frozenset(
        {
            Permission.BILLING_READ,
            Permission.BILLING_WRITE,
            Permission.ANALYTICS_READ,
            Permission.PAYMENT_ANALYTICS_READ,
            Permission.AUDIT_READ,
        }
    ),
    TenantRole.SUPPORT_AGENT: frozenset(
        {
            Permission.WORKFLOW_READ,
            Permission.ANALYTICS_READ,
            Permission.CONVERSATION_PII_READ,
            Permission.RECORDING_READ,
            Permission.TRANSCRIPT_READ,
            Permission.CAMPAIGN_READ,
        }
    ),
    TenantRole.DEVELOPER: frozenset(
        {
            Permission.WORKFLOW_READ,
            Permission.WORKFLOW_WRITE,
            Permission.WORKFLOW_EXECUTE,
            Permission.CONFIG_READ,
            Permission.CONFIG_WRITE,
            Permission.API_KEY_READ,
            Permission.API_KEY_WRITE,
            Permission.TOOL_READ,
            Permission.TOOL_MANAGE,
            Permission.TOOL_INVOKE,
            Permission.CAMPAIGN_READ,
        }
    ),
}

_ASSIGNABLE_ROLES: dict[TenantRole, FrozenSet[TenantRole]] = {
    TenantRole.OWNER: frozenset(TenantRole),
    TenantRole.ADMIN: frozenset(
        r
        for r in TenantRole
        if r not in {TenantRole.OWNER}
    ),
    TenantRole.OPERATOR: frozenset(),
    TenantRole.OPERATIONS_MANAGER: frozenset(
        {
            TenantRole.SUPPORT_AGENT,
            TenantRole.ANALYST,
            TenantRole.VIEWER,
            TenantRole.READ_ONLY,
        }
    ),
    TenantRole.AGENT_MANAGER: frozenset({TenantRole.SUPPORT_AGENT, TenantRole.VIEWER}),
    TenantRole.ANALYST: frozenset(),
    TenantRole.VIEWER: frozenset(),
    TenantRole.READ_ONLY: frozenset(),
    TenantRole.BILLING: frozenset(),
    TenantRole.FINANCE: frozenset(),
    TenantRole.SUPPORT_AGENT: frozenset(),
    TenantRole.DEVELOPER: frozenset(),
}


def permissions_for_role(role: TenantRole | str) -> FrozenSet[Permission]:
    parsed = role if isinstance(role, TenantRole) else TenantRole(role)
    return _ROLE_PERMISSIONS.get(parsed, frozenset())


def can_assign_role(actor_role: TenantRole, target_role: TenantRole) -> bool:
    allowed = _ASSIGNABLE_ROLES.get(actor_role, frozenset())
    return target_role in allowed


def default_role_for_new_member(is_first_member: bool) -> TenantRole:
    return TenantRole.OWNER if is_first_member else TenantRole.VIEWER


permissions_for_role = permissions_for_role
can_assign_role = can_assign_role
default_role_for_new_member = default_role_for_new_member


def sensitive_permissions() -> FrozenSet[Permission]:
    return _PII_SURFACE | {
        Permission.PAYMENT_ANALYTICS_READ,
        Permission.API_KEY_WRITE,
        Permission.SECURITY_ADMIN,
        Permission.TOOL_MANAGE,
        Permission.TOOL_INVOKE,
    }
