"""Multi-tenant isolation, RBAC, and configuration."""

from api.services.tenant.rbac import can_assign_role, permissions_for_role
from api.services.tenant.types import Permission, TenantContext, TenantRole

__all__ = [
    "AnalyticsReadContext",
    "Permission",
    "TenantAccessDenied",
    "TenantContext",
    "TenantContextDep",
    "TenantIsolationViolation",
    "TenantMiddleware",
    "TenantRole",
    "TenantService",
    "assert_campaign_belongs_to_tenant",
    "assert_customer_belongs_to_tenant",
    "assert_same_tenant",
    "assert_session_belongs_to_tenant",
    "assert_workflow_run_belongs_to_tenant",
    "can_assign_role",
    "get_tenant_context",
    "get_tenant_service",
    "lookup_session_organization_id",
    "permissions_for_role",
    "register_session_organization",
    "require_permission",
    "resolve_tenant_context",
    "scoped_organization_id",
]

_LAZY_EXPORTS = {
    "AnalyticsReadContext": "api.services.tenant.route_helpers",
    "TenantContextDep": "api.services.tenant.route_helpers",
    "TenantAccessDenied": "api.services.tenant.access_control",
    "TenantIsolationViolation": "api.services.tenant.access_control",
    "assert_campaign_belongs_to_tenant": "api.services.tenant.session_tenant",
    "assert_customer_belongs_to_tenant": "api.services.tenant.session_tenant",
    "assert_same_tenant": "api.services.tenant.access_control",
    "assert_session_belongs_to_tenant": "api.services.tenant.session_tenant",
    "assert_workflow_run_belongs_to_tenant": "api.services.tenant.session_tenant",
    "get_tenant_context": "api.services.tenant.access_control",
    "lookup_session_organization_id": "api.services.tenant.session_tenant",
    "register_session_organization": "api.services.tenant.session_tenant",
    "require_permission": "api.services.tenant.access_control",
    "resolve_tenant_context": "api.services.tenant.access_control",
    "scoped_organization_id": "api.services.tenant.access_control",
    "TenantMiddleware": "api.services.tenant.middleware",
    "TenantService": "api.services.tenant.service",
    "get_tenant_service": "api.services.tenant.service",
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(_LAZY_EXPORTS[name])
    return getattr(module, name)
