"""Database operations for customer timeline entries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.dialects.postgresql import insert

from api.db.base_client import BaseDBClient
from api.db.models import CustomerTimelineEntryModel


class CustomerTimelineClient(BaseDBClient):
    async def upsert_customer_timeline_entry(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        customer_id: int | None,
        channel: str,
        event_type: str,
        title: str,
        summary: str | None,
        payload: dict[str, Any],
        workflow_run_id: int | None,
        conversation_id: int | None,
        transaction_id: int | None,
        correlation_id: str | None,
        journey_state: str | None,
        occurred_at: datetime,
        platform_event_id: int | None,
        idempotency_key: str,
    ) -> CustomerTimelineEntryModel | None:
        async with self.async_session() as session:
            stmt = (
                insert(CustomerTimelineEntryModel)
                .values(
                    organization_id=organization_id,
                    customer_id=customer_id,
                    phone_e164=phone_e164,
                    channel=channel,
                    event_type=event_type,
                    title=title,
                    summary=summary,
                    payload=payload,
                    workflow_run_id=workflow_run_id,
                    conversation_id=conversation_id,
                    transaction_id=transaction_id,
                    correlation_id=correlation_id,
                    journey_state=journey_state,
                    occurred_at=occurred_at,
                    platform_event_id=platform_event_id,
                    idempotency_key=idempotency_key,
                )
                .on_conflict_do_nothing(index_elements=["idempotency_key"])
                .returning(CustomerTimelineEntryModel)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                existing = await session.execute(
                    select(CustomerTimelineEntryModel).where(
                        CustomerTimelineEntryModel.idempotency_key == idempotency_key
                    )
                )
                row = existing.scalar_one_or_none()
            await session.commit()
            if row and row.id:
                await session.refresh(row)
            return row

    async def list_customer_timeline_entries(
        self,
        *,
        organization_id: int,
        phone_e164: str | None = None,
        customer_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 100,
    ) -> list[CustomerTimelineEntryModel]:
        async with self.async_session() as session:
            query = select(CustomerTimelineEntryModel).where(
                CustomerTimelineEntryModel.organization_id == organization_id
            )
            if phone_e164 and customer_id:
                query = query.where(
                    or_(
                        CustomerTimelineEntryModel.phone_e164 == phone_e164,
                        CustomerTimelineEntryModel.customer_id == customer_id,
                    )
                )
            elif phone_e164:
                query = query.where(CustomerTimelineEntryModel.phone_e164 == phone_e164)
            elif customer_id:
                query = query.where(CustomerTimelineEntryModel.customer_id == customer_id)
            if from_ts is not None:
                query = query.where(CustomerTimelineEntryModel.occurred_at >= from_ts)
            if to_ts is not None:
                query = query.where(CustomerTimelineEntryModel.occurred_at <= to_ts)
            query = query.order_by(desc(CustomerTimelineEntryModel.occurred_at)).limit(
                limit
            )
            result = await session.execute(query)
            return list(result.scalars().all())
