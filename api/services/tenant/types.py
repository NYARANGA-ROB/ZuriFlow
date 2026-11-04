"""Tenant domain types: roles, permissions, and context."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet


class TenantRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    OPERATIONS_MANAGER = "operations_manager"
    AGENT_MANAGER = "agent_manager"
    ANALYST = "analyst"
    VIEWER = "viewer"
    READ_ONLY = "read_only"
    BILLING = "billing"
    FINANCE = "finance"
    SUPPORT_AGENT = "support_agent"
    DEVELOPER = "developer"


class Permission(str, Enum):
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    WORKFLOW_EXECUTE = "workflow:execute"
    CAMPAIGN_READ = "campaign:read"
    CAMPAIGN_WRITE = "campaign:write"
    ANALYTICS_READ = "analytics:read"
    CONVERSATION_PII_READ = "conversation_pii:read"
    RECORDING_READ = "recording:read"
    TRANSCRIPT_READ = "transcript:read"
    PAYMENT_ANALYTICS_READ = "payment_analytics:read"
    BILLING_READ = "billing:read"
    BILLING_WRITE = "billing:write"
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    MEMBER_READ = "member:read"
    MEMBER_WRITE = "member:write"
    API_KEY_READ = "api_key:read"
    API_KEY_WRITE = "api_key:write"
    TOOL_READ = "tool:read"
    TOOL_MANAGE = "tool:manage"
    TOOL_INVOKE = "tool:invoke"
    AUDIT_READ = "audit:read"
    SECURITY_ADMIN = "security:admin"
    TENANT_ADMIN = "tenant:admin"


@dataclass(frozen=True)
class TenantContext:
    """Resolved tenant scope for the current request."""

    organization_id: int
    user_id: int
    role: TenantRole
    permissions: FrozenSet[Permission] = field(default_factory=frozenset)
    is_superuser: bool = False
    billing_enabled: bool = True

    def has_permission(self, permission: Permission | str) -> bool:
        if self.is_superuser:
            return True
        key = permission if isinstance(permission, Permission) else Permission(permission)
        return key in self.permissions or Permission.TENANT_ADMIN in self.permissions

    def require_permission(self, permission: Permission | str) -> None:
        from api.services.tenant.access_control import TenantAccessDenied

        if not self.has_permission(permission):
            raise TenantAccessDenied(
                f"Missing permission: {permission}",
                organization_id=self.organization_id,
                permission=str(permission),
            )
