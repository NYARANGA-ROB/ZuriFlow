"""Organization-level administrative audit logging."""

from __future__ import annotations

from typing import Any

from api.db import db_client

WORKFLOW_CHANGED = "workflow_changed"
PAYMENT_SETTINGS_CHANGED = "payment_settings_changed"
USER_INVITED = "user_invited"
INTEGRATION_ADDED = "integration_added"
AGENT_PUBLISHED = "agent_published"
API_CREDENTIAL_CHANGED = "api_credential_changed"


async def log_admin_action(
    *,
    organization_id: int,
    action: str,
    resource_type: str,
    actor_user_id: int | None = None,
    resource_id: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await db_client.append_organization_audit_log(
        organization_id=organization_id,
        action=action,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
        resource_id=resource_id,
        summary=summary,
        metadata_json=metadata or {},
    )
