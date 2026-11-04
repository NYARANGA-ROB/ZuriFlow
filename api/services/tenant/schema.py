"""Pydantic schemas for tenant APIs and configuration."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from api.services.tenant.types import Permission, TenantRole


class TenantMemberSchema(BaseModel):
    user_id: int
    role: TenantRole
    email: Optional[str] = None
    created_at: Optional[str] = None


class TenantContextResponse(BaseModel):
    organization_id: int
    user_id: int
    role: TenantRole
    permissions: List[str]
    billing_enabled: bool
    isolation_enabled: bool


class UpdateMemberRoleRequest(BaseModel):
    role: TenantRole


class AddMemberRequest(BaseModel):
    user_id: int
    role: TenantRole = TenantRole.VIEWER


class TenantWorkflowDefaults(BaseModel):
    default_locale: str = "en"
    vertical_template_id: Optional[str] = None
    auto_escalation: bool = False


class TenantFeatureFlags(BaseModel):
    debt_collection: bool = True
    voice_campaigns: bool = True
    business_analytics: bool = True
    crm_integration: bool = True
    human_escalation: bool = True


class TenantBillingSettings(BaseModel):
    plan_id: str = "starter"
    mps_billing_enabled: bool = True
    price_per_second_usd: Optional[float] = None
    quota_enforcement: Literal["soft", "hard", "none"] = "soft"
    subscription_status: Literal[
        "active", "trialing", "past_due", "suspended", "cancelled"
    ] = "trialing"


class TenantBrandingSettings(BaseModel):
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    custom_domain: Optional[str] = None
    email_from_name: Optional[str] = None
    email_from_address: Optional[str] = None
    agent_display_name: Optional[str] = None
    agent_voice_intro: Optional[str] = None


class TenantEnterpriseSettings(BaseModel):
    sso_protocol: Literal["none", "oidc", "saml"] = "none"
    sso_issuer: Optional[str] = None
    sso_client_id: Optional[str] = None
    custom_domain: Optional[str] = None
    dedicated_phone_numbers: bool = False
    dedicated_infrastructure: bool = False
    sla_tier: Optional[str] = None
    api_access: bool = True
    webhooks: bool = True


class TenantConfigurationSchema(BaseModel):
    """Tenant-scoped settings stored under OrganizationConfigurationKey.TENANT_CONFIGURATION."""

    isolation_mode: Literal["strict", "standard"] = "strict"
    analytics_retention_days: int = Field(default=90, ge=1, le=3650)
    workflow_defaults: TenantWorkflowDefaults = Field(
        default_factory=TenantWorkflowDefaults
    )
    feature_flags: TenantFeatureFlags = Field(default_factory=TenantFeatureFlags)
    billing: TenantBillingSettings = Field(default_factory=TenantBillingSettings)
    branding: TenantBrandingSettings = Field(default_factory=TenantBrandingSettings)
    enterprise: TenantEnterpriseSettings = Field(
        default_factory=TenantEnterpriseSettings
    )
    custom: Dict[str, Any] = Field(default_factory=dict)


class TenantConfigUpdateRequest(BaseModel):
    configuration: TenantConfigurationSchema


class TenantAnalyticsSummary(BaseModel):
    organization_id: int
    from_ts: float
    to_ts: float
    total_calls: int = 0
    active_workflows: int = 0
    member_count: int = 0
    billing_plan: str = "standard"
    metrics: Dict[str, Any] = Field(default_factory=dict)


class TenantBillingSnapshot(BaseModel):
    organization_id: int
    billing_enabled: bool
    plan_id: str
    price_per_second_usd: Optional[float] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    used_dograh_tokens: Optional[float] = None
    total_duration_seconds: Optional[int] = None


class RolePermissionsResponse(BaseModel):
    role: TenantRole
    permissions: List[Permission]
