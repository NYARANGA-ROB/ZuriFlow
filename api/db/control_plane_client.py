"""Database access for SaaS control-plane knowledge and audit logs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from api.db.base_client import BaseDBClient
from api.db.models import BusinessKnowledgeEntryModel, OrganizationAuditLogModel


class ControlPlaneClient(BaseDBClient):
    async def create_business_knowledge_entry(
        self,
        *,
        organization_id: int,
        category: str,
        title: str,
        content: str,
        metadata_json: dict[str, Any] | None = None,
        document_uuid: str | None = None,
        created_by_user_id: int | None = None,
    ) -> BusinessKnowledgeEntryModel:
        async with self.async_session() as session:
            row = BusinessKnowledgeEntryModel(
                organization_id=organization_id,
                category=category,
                title=title,
                content=content,
                metadata_json=metadata_json or {},
                document_uuid=document_uuid,
                created_by_user_id=created_by_user_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_business_knowledge_entries(
        self,
        organization_id: int,
        *,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[BusinessKnowledgeEntryModel]:
        async with self.async_session() as session:
            stmt = select(BusinessKnowledgeEntryModel).where(
                BusinessKnowledgeEntryModel.organization_id == organization_id
            )
            if category:
                stmt = stmt.where(BusinessKnowledgeEntryModel.category == category)
            if active_only:
                stmt = stmt.where(BusinessKnowledgeEntryModel.is_active.is_(True))
            stmt = stmt.order_by(BusinessKnowledgeEntryModel.updated_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_business_knowledge_entry(
        self, organization_id: int, entry_id: int
    ) -> BusinessKnowledgeEntryModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessKnowledgeEntryModel).where(
                    BusinessKnowledgeEntryModel.id == entry_id,
                    BusinessKnowledgeEntryModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def update_business_knowledge_entry(
        self,
        organization_id: int,
        entry_id: int,
        **fields: Any,
    ) -> BusinessKnowledgeEntryModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessKnowledgeEntryModel).where(
                    BusinessKnowledgeEntryModel.id == entry_id,
                    BusinessKnowledgeEntryModel.organization_id == organization_id,
                )
            )
            row = result.scalars().first()
            if not row:
                return None
            for key, value in fields.items():
                if value is not None and hasattr(row, key):
                    setattr(row, key, value)
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return row

    async def search_business_knowledge_entries(
        self,
        organization_id: int,
        query: str,
        *,
        limit: int = 5,
    ) -> list[BusinessKnowledgeEntryModel]:
        tokens = [t for t in query.lower().split() if len(t) > 1][:8]
        async with self.async_session() as session:
            stmt = select(BusinessKnowledgeEntryModel).where(
                BusinessKnowledgeEntryModel.organization_id == organization_id,
                BusinessKnowledgeEntryModel.is_active.is_(True),
                BusinessKnowledgeEntryModel.status.notin_(["expired", "deprecated", "rejected"]),
                BusinessKnowledgeEntryModel.is_approved.is_(True),
            )
            if tokens:
                filters = []
                for token in tokens:
                    like = f"%{token}%"
                    filters.append(BusinessKnowledgeEntryModel.title.ilike(like))
                    filters.append(BusinessKnowledgeEntryModel.content.ilike(like))
                    filters.append(BusinessKnowledgeEntryModel.category.ilike(like))
                stmt = stmt.where(or_(*filters))
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def append_organization_audit_log(
        self,
        *,
        organization_id: int,
        action: str,
        resource_type: str,
        actor_user_id: int | None = None,
        resource_id: str | None = None,
        summary: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> OrganizationAuditLogModel:
        async with self.async_session() as session:
            row = OrganizationAuditLogModel(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                summary=summary,
                metadata_json=metadata_json or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_organization_audit_logs(
        self,
        organization_id: int,
        *,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OrganizationAuditLogModel]:
        async with self.async_session() as session:
            stmt = select(OrganizationAuditLogModel).where(
                OrganizationAuditLogModel.organization_id == organization_id
            )
            if action:
                stmt = stmt.where(OrganizationAuditLogModel.action == action)
            stmt = (
                stmt.order_by(OrganizationAuditLogModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
