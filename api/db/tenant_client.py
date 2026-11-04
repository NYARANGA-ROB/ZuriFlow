"""Database operations for organization membership and RBAC."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from api.db.base_client import BaseDBClient
from api.db.models import OrganizationMemberModel, UserModel
from api.services.tenant.rbac import default_role_for_new_member
from api.services.tenant.types import TenantRole


class TenantClient(BaseDBClient):
    async def get_organization_member(
        self, organization_id: int, user_id: int
    ) -> Optional[OrganizationMemberModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationMemberModel).where(
                    OrganizationMemberModel.organization_id == organization_id,
                    OrganizationMemberModel.user_id == user_id,
                )
            )
            return result.scalars().first()

    async def list_organization_members(
        self, organization_id: int
    ) -> list[OrganizationMemberModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationMemberModel)
                .where(OrganizationMemberModel.organization_id == organization_id)
                .order_by(OrganizationMemberModel.created_at.asc())
            )
            return list(result.scalars().all())

    async def count_organization_members(self, organization_id: int) -> int:
        async with self.async_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(OrganizationMemberModel)
                .where(OrganizationMemberModel.organization_id == organization_id)
            )
            return int(result.scalar() or 0)

    async def ensure_organization_member(
        self,
        organization_id: int,
        user_id: int,
        *,
        role: TenantRole | str | None = None,
    ) -> OrganizationMemberModel:
        """Create membership if missing; does not downgrade an existing role."""
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationMemberModel).where(
                    OrganizationMemberModel.organization_id == organization_id,
                    OrganizationMemberModel.user_id == user_id,
                )
            )
            existing = result.scalars().first()
            if existing:
                return existing

            count_result = await session.execute(
                select(func.count())
                .select_from(OrganizationMemberModel)
                .where(OrganizationMemberModel.organization_id == organization_id)
            )
            is_first = int(count_result.scalar() or 0) == 0
            resolved_role = (
                TenantRole(role) if role else default_role_for_new_member(is_first)
            )

            member = OrganizationMemberModel(
                organization_id=organization_id,
                user_id=user_id,
                role=resolved_role.value,
            )
            session.add(member)
            await session.commit()
            await session.refresh(member)
            return member

    async def upsert_organization_member_role(
        self,
        organization_id: int,
        user_id: int,
        role: TenantRole | str,
    ) -> OrganizationMemberModel:
        parsed = role if isinstance(role, TenantRole) else TenantRole(role)
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationMemberModel).where(
                    OrganizationMemberModel.organization_id == organization_id,
                    OrganizationMemberModel.user_id == user_id,
                )
            )
            member = result.scalars().first()
            if member is None:
                member = OrganizationMemberModel(
                    organization_id=organization_id,
                    user_id=user_id,
                    role=parsed.value,
                )
                session.add(member)
            else:
                member.role = parsed.value
                member.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(member)
            return member

    async def remove_organization_member(
        self, organization_id: int, user_id: int
    ) -> bool:
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationMemberModel).where(
                    OrganizationMemberModel.organization_id == organization_id,
                    OrganizationMemberModel.user_id == user_id,
                )
            )
            member = result.scalars().first()
            if not member:
                return False
            await session.delete(member)
            await session.commit()
            return True

    async def list_members_with_users(
        self, organization_id: int
    ) -> list[tuple[OrganizationMemberModel, UserModel | None]]:
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationMemberModel, UserModel)
                .outerjoin(UserModel, UserModel.id == OrganizationMemberModel.user_id)
                .where(OrganizationMemberModel.organization_id == organization_id)
                .order_by(OrganizationMemberModel.created_at.asc())
            )
            return list(result.all())

    async def backfill_member_from_association(
        self, organization_id: int, user_id: int
    ) -> None:
        """Idempotent helper used when linking users via organization_users."""
        stmt = insert(OrganizationMemberModel.__table__).values(
            organization_id=organization_id,
            user_id=user_id,
            role=TenantRole.VIEWER.value,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["organization_id", "user_id"]
        )
        async with self.async_session() as session:
            await session.execute(stmt)
            await session.commit()
