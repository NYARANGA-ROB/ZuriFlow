from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy.future import select

from api.db.base_client import BaseDBClient
from api.db.models import MpesaTransactionEventModel, MpesaTransactionModel


class MpesaClient(BaseDBClient):
    async def create_transaction(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        amount: float,
        account_reference: str,
        transaction_desc: str,
        workflow_run_id: int | None = None,
        currency: str = "KES",
        metadata: dict[str, Any] | None = None,
    ) -> MpesaTransactionModel:
        async with self.async_session() as session:
            tx = MpesaTransactionModel(
                organization_id=organization_id,
                workflow_run_id=workflow_run_id,
                phone_e164=phone_e164,
                amount=amount,
                currency=currency,
                account_reference=account_reference,
                transaction_desc=transaction_desc,
                metadata_json=metadata or {},
            )
            session.add(tx)
            await session.commit()
            await session.refresh(tx)
            return tx

    async def get_transaction(
        self,
        transaction_id: int,
        *,
        organization_id: int,
    ) -> MpesaTransactionModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(MpesaTransactionModel)
                .where(MpesaTransactionModel.id == transaction_id)
                .where(MpesaTransactionModel.organization_id == organization_id)
            )
            return result.scalars().first()

    async def get_transaction_by_checkout_request_id(
        self,
        checkout_request_id: str,
        *,
        organization_id: int | None = None,
    ) -> MpesaTransactionModel | None:
        async with self.async_session() as session:
            query = select(MpesaTransactionModel).where(
                MpesaTransactionModel.checkout_request_id == checkout_request_id
            )
            if organization_id is not None:
                query = query.where(MpesaTransactionModel.organization_id == organization_id)
            result = await session.execute(query)
            return result.scalars().first()

    async def list_transactions(
        self,
        *,
        organization_id: int,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MpesaTransactionModel]:
        async with self.async_session() as session:
            query = (
                select(MpesaTransactionModel)
                .where(MpesaTransactionModel.organization_id == organization_id)
                .order_by(desc(MpesaTransactionModel.created_at))
                .limit(limit)
                .offset(offset)
            )
            if status:
                query = query.where(MpesaTransactionModel.status == status)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_transaction(
        self,
        transaction_id: int,
        *,
        organization_id: int,
        **fields: Any,
    ) -> MpesaTransactionModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(MpesaTransactionModel)
                .where(MpesaTransactionModel.id == transaction_id)
                .where(MpesaTransactionModel.organization_id == organization_id)
                .with_for_update()
            )
            tx = result.scalars().first()
            if not tx:
                return None

            for key, value in fields.items():
                if key == "metadata" and value is not None:
                    merged = dict(tx.metadata_json or {})
                    merged.update(value)
                    tx.metadata_json = merged
                elif hasattr(tx, key):
                    setattr(tx, key, value)

            await session.commit()
            await session.refresh(tx)

            try:
                from api.services.tenant_billing.hooks import on_mpesa_transaction_updated

                await on_mpesa_transaction_updated(tx)
            except Exception:
                pass

            return tx

    async def append_event(
        self,
        *,
        transaction_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> MpesaTransactionEventModel:
        async with self.async_session() as session:
            event = MpesaTransactionEventModel(
                transaction_id=transaction_id,
                event_type=event_type,
                payload=payload or {},
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event

    async def list_events(
        self,
        *,
        transaction_id: int,
        organization_id: int,
        limit: int = 100,
    ) -> list[MpesaTransactionEventModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(MpesaTransactionEventModel)
                .join(MpesaTransactionModel)
                .where(MpesaTransactionEventModel.transaction_id == transaction_id)
                .where(MpesaTransactionModel.organization_id == organization_id)
                .order_by(MpesaTransactionEventModel.created_at)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def list_pending_for_verification(
        self,
        *,
        older_than: datetime,
        limit: int = 50,
    ) -> list[MpesaTransactionModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(MpesaTransactionModel)
                .where(MpesaTransactionModel.status.in_(("initiated", "pending")))
                .where(MpesaTransactionModel.checkout_request_id.isnot(None))
                .where(MpesaTransactionModel.created_at <= older_than)
                .order_by(MpesaTransactionModel.created_at)
                .limit(limit)
            )
            return list(result.scalars().all())
