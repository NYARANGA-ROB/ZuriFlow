"""CRM audit logging."""

from __future__ import annotations

from typing import Any

from api.db import db_client


class CrmAuditLogger:
    """Append-only audit trail for CRM mutations and profile access."""

    async def log(
        self,
        *,
        organization_id: int,
        action: str,
        resource_type: str,
        customer_id: int | None = None,
        actor_user_id: int | None = None,
        resource_id: str | None = None,
        changes: dict[str, Any] | None = None,
        ip_address: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await db_client.append_audit_log(
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            customer_id=customer_id,
            actor_user_id=actor_user_id,
            resource_id=resource_id,
            changes=changes,
            ip_address=ip_address,
            metadata=metadata,
        )


_audit: CrmAuditLogger | None = None


def get_crm_audit_logger() -> CrmAuditLogger:
    global _audit
    if _audit is None:
        _audit = CrmAuditLogger()
    return _audit
