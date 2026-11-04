from typing import Any

from sqlalchemy import select

from api.db.base_client import BaseDBClient
from api.db.models import SecurityAuditEventModel


class SecurityAuditClient(BaseDBClient):
    async def append_security_audit_event(
        self,
        *,
        action: str,
        resource_type: str,
        outcome: str = "success",
        organization_id: int | None = None,
        actor_user_id: int | None = None,
        resource_id: str | None = None,
        summary: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> SecurityAuditEventModel:
        async with self.async_session() as session:
            row = SecurityAuditEventModel(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                summary=summary,
                metadata_json=metadata_json or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_security_audit_events(
        self,
        organization_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SecurityAuditEventModel]:
        async with self.async_session() as session:
            stmt = (
                select(SecurityAuditEventModel)
                .where(SecurityAuditEventModel.organization_id == organization_id)
                .order_by(SecurityAuditEventModel.id.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
