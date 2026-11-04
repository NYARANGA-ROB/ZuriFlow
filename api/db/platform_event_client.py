"""Database operations for platform events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert

from api.db.base_client import BaseDBClient
from api.db.models import PlatformEventModel


class PlatformEventClient(BaseDBClient):
    async def insert_platform_event(
        self,
        *,
        event_id: str,
        organization_id: int | None,
        event_type: str,
        source: str,
        correlation_id: str | None,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> PlatformEventModel | None:
        async with self.async_session() as session:
            if idempotency_key:
                stmt = (
                    insert(PlatformEventModel)
                    .values(
                        event_id=event_id,
                        organization_id=organization_id,
                        event_type=event_type,
                        source=source,
                        correlation_id=correlation_id,
                        payload=payload,
                        idempotency_key=idempotency_key,
                    )
                    .on_conflict_do_nothing(index_elements=["idempotency_key"])
                    .returning(PlatformEventModel)
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row is None:
                    existing = await session.execute(
                        select(PlatformEventModel).where(
                            PlatformEventModel.idempotency_key == idempotency_key
                        )
                    )
                    row = existing.scalar_one_or_none()
                await session.commit()
                if row and row.id:
                    await session.refresh(row)
                return row

            row = PlatformEventModel(
                event_id=event_id,
                organization_id=organization_id,
                event_type=event_type,
                source=source,
                correlation_id=correlation_id,
                payload=payload,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_platform_event(self, event_id: str) -> PlatformEventModel | None:
        async with self.async_session() as session:
            by_uuid = await session.execute(
                select(PlatformEventModel).where(
                    PlatformEventModel.event_id == event_id
                )
            )
            row = by_uuid.scalar_one_or_none()
            if row:
                return row
            try:
                pk = int(event_id)
            except ValueError:
                return None
            by_pk = await session.execute(
                select(PlatformEventModel).where(PlatformEventModel.id == pk)
            )
            return by_pk.scalar_one_or_none()

    async def get_platform_event_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> PlatformEventModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(PlatformEventModel).where(
                    PlatformEventModel.idempotency_key == idempotency_key
                )
            )
            return result.scalar_one_or_none()

    async def list_platform_events(
        self,
        *,
        organization_id: int | None = None,
        event_type: str | None = None,
        correlation_id: str | None = None,
        since_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 100,
    ) -> list[PlatformEventModel]:
        async with self.async_session() as session:
            query = select(PlatformEventModel)
            if organization_id is not None:
                query = query.where(PlatformEventModel.organization_id == organization_id)
            if event_type:
                query = query.where(PlatformEventModel.event_type == event_type)
            if correlation_id:
                query = query.where(PlatformEventModel.correlation_id == correlation_id)
            if since_id is not None:
                query = query.where(PlatformEventModel.id > since_id)
            if from_ts is not None:
                query = query.where(PlatformEventModel.created_at >= from_ts)
            if to_ts is not None:
                query = query.where(PlatformEventModel.created_at <= to_ts)
            query = query.order_by(PlatformEventModel.id.asc()).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def count_platform_events(
        self,
        *,
        organization_id: int,
        event_type: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> int:
        from sqlalchemy import func

        async with self.async_session() as session:
            query = select(func.count(PlatformEventModel.id)).where(
                PlatformEventModel.organization_id == organization_id
            )
            if event_type:
                query = query.where(PlatformEventModel.event_type == event_type)
            if from_ts is not None:
                query = query.where(PlatformEventModel.created_at >= from_ts)
            if to_ts is not None:
                query = query.where(PlatformEventModel.created_at <= to_ts)
            result = await session.execute(query)
            return int(result.scalar_one() or 0)
