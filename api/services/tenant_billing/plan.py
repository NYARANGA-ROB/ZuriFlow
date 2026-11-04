"""Load tenant billing plan from organization configuration."""

from __future__ import annotations

from api.db import db_client
from api.enums import OrganizationConfigurationKey
from api.services.tenant.config import load_tenant_configuration
from api.services.tenant.schema import TenantBillingSettings
from api.services.tenant_billing.catalog import plan_from_catalog
from api.services.tenant_billing.schema import TenantBillingPlanSchema


async def load_billing_plan(organization_id: int) -> TenantBillingPlanSchema:
    row = await db_client.get_configuration(
        organization_id,
        OrganizationConfigurationKey.TENANT_CONFIGURATION.value,
    )
    if not row or not row.value:
        return TenantBillingPlanSchema()

    billing = (row.value or {}).get("billing") or {}
    custom = billing.get("usage_billing") or {}
    if custom:
        return TenantBillingPlanSchema.model_validate(custom)

    tenant_billing = TenantBillingSettings.model_validate(billing)
    catalog_plan = plan_from_catalog(tenant_billing.plan_id)
    return TenantBillingPlanSchema(
        plan_id=tenant_billing.plan_id,
        currency=catalog_plan.currency,
        rates=catalog_plan.rates,
        quotas=catalog_plan.quotas,
        subscription={
            "status": tenant_billing.subscription_status,
            "tier": tenant_billing.plan_id,
        },
    )


async def save_billing_plan(
    organization_id: int, plan: TenantBillingPlanSchema
) -> TenantBillingPlanSchema:
    config = await load_tenant_configuration(organization_id)
    payload = config.model_dump(mode="json")
    billing = dict(payload.get("billing") or {})
    billing["usage_billing"] = plan.model_dump(mode="json")
    billing["subscription_status"] = plan.subscription.status.value
    payload["billing"] = billing
    from api.services.tenant.config import save_tenant_configuration

    await save_tenant_configuration(organization_id, payload)
    return plan


async def get_subscription_status(organization_id: int) -> str:
    plan = await load_billing_plan(organization_id)
    return plan.subscription.status.value
