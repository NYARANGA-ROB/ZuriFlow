"""Tenant configuration load/save backed by organization_configurations."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.enums import OrganizationConfigurationKey
from api.services.tenant.schema import TenantConfigurationSchema


async def load_tenant_configuration(
    organization_id: int,
) -> TenantConfigurationSchema:
    row = await db_client.get_configuration(
        organization_id, OrganizationConfigurationKey.TENANT_CONFIGURATION.value
    )
    if not row or not row.value:
        return TenantConfigurationSchema()
    return TenantConfigurationSchema.model_validate(row.value)


async def save_tenant_configuration(
    organization_id: int,
    configuration: TenantConfigurationSchema | dict[str, Any],
) -> TenantConfigurationSchema:
    if isinstance(configuration, TenantConfigurationSchema):
        payload = configuration.model_dump(mode="json")
    else:
        payload = TenantConfigurationSchema.model_validate(configuration).model_dump(
            mode="json"
        )
    await db_client.upsert_configuration(
        organization_id,
        OrganizationConfigurationKey.TENANT_CONFIGURATION.value,
        payload,
    )
    return TenantConfigurationSchema.model_validate(payload)


def is_feature_enabled(
    configuration: TenantConfigurationSchema,
    feature: str,
) -> bool:
    flags = configuration.feature_flags
    return bool(getattr(flags, feature, True))
