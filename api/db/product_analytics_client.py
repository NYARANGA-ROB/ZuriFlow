"""Organization-scoped product analytics (activation and retention)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select

from api.db.base_client import BaseDBClient
from api.db.models import ProductAnalyticsEventModel


class ProductAnalyticsClient(BaseDBClient):
    async def insert_product_event(
        self,
        *,
        organization_id: int,
        event_name: str,
        properties: dict[str, Any] | None = None,
    ) -> ProductAnalyticsEventModel:
        async with self.async_session() as session:
            row = ProductAnalyticsEventModel(
                organization_id=organization_id,
                event_name=event_name,
                properties=properties or {},
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def has_product_event(
        self, organization_id: int, event_name: str
    ) -> bool:
        async with self.async_session() as session:
            result = await session.execute(
                select(ProductAnalyticsEventModel.id)
                .where(
                    ProductAnalyticsEventModel.organization_id == organization_id,
                    ProductAnalyticsEventModel.event_name == event_name,
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def count_product_events(
        self, organization_id: int
    ) -> dict[str, int]:
        async with self.async_session() as session:
            result = await session.execute(
                select(
                    ProductAnalyticsEventModel.event_name,
                    func.count(ProductAnalyticsEventModel.id),
                )
                .where(ProductAnalyticsEventModel.organization_id == organization_id)
                .group_by(ProductAnalyticsEventModel.event_name)
            )
            return {name: int(count) for name, count in result.all()}

    async def recent_product_events(
        self, organization_id: int, *, limit: int = 50
    ) -> list[ProductAnalyticsEventModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(ProductAnalyticsEventModel)
                .where(ProductAnalyticsEventModel.organization_id == organization_id)
                .order_by(desc(ProductAnalyticsEventModel.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())
