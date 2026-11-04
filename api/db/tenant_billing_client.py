"""Database operations for tenant usage billing."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from api.db.base_client import BaseDBClient
from api.db.models import (
    TenantBillingQuotaModel,
    TenantInvoiceLineModel,
    TenantInvoiceModel,
    TenantUsageEventModel,
)


class TenantBillingClient(BaseDBClient):
    async def record_usage_event(
        self,
        *,
        organization_id: int,
        metric_code: str,
        quantity: float,
        unit: str,
        aggregation_key: str,
        recorded_at: datetime,
        billable_amount: float | None = None,
        unit_cost: float | None = None,
        billing_period: str | None = None,
        currency: str = "USD",
        workflow_run_id: int | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TenantUsageEventModel | None:
        """Insert a usage event; skip silently on duplicate aggregation_key."""
        async with self.async_session() as session:
            stmt = (
                insert(TenantUsageEventModel)
                .values(
                    organization_id=organization_id,
                    metric_code=metric_code,
                    quantity=quantity,
                    unit=unit,
                    billable_amount=billable_amount,
                    unit_cost=unit_cost,
                    billing_period=billing_period,
                    currency=currency,
                    workflow_run_id=workflow_run_id,
                    reference_type=reference_type,
                    reference_id=reference_id,
                    aggregation_key=aggregation_key,
                    metadata_json=metadata or {},
                    recorded_at=recorded_at,
                )
                .on_conflict_do_nothing(index_elements=["aggregation_key"])
                .returning(TenantUsageEventModel)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.scalars().first()

    async def sum_usage(
        self,
        organization_id: int,
        *,
        metric_code: str | None = None,
        from_ts: datetime,
        to_ts: datetime,
    ) -> float:
        async with self.async_session() as session:
            query = select(func.coalesce(func.sum(TenantUsageEventModel.quantity), 0.0)).where(
                TenantUsageEventModel.organization_id == organization_id,
                TenantUsageEventModel.recorded_at >= from_ts,
                TenantUsageEventModel.recorded_at <= to_ts,
            )
            if metric_code:
                query = query.where(TenantUsageEventModel.metric_code == metric_code)
            result = await session.execute(query)
            return float(result.scalar_one() or 0.0)

    async def aggregate_usage_by_metric(
        self,
        organization_id: int,
        *,
        from_ts: datetime,
        to_ts: datetime,
    ) -> dict[str, dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(
                select(
                    TenantUsageEventModel.metric_code,
                    TenantUsageEventModel.unit,
                    func.coalesce(func.sum(TenantUsageEventModel.quantity), 0.0).label(
                        "total_quantity"
                    ),
                    func.coalesce(func.sum(TenantUsageEventModel.billable_amount), 0.0).label(
                        "total_amount"
                    ),
                    func.count(TenantUsageEventModel.id).label("event_count"),
                )
                .where(
                    TenantUsageEventModel.organization_id == organization_id,
                    TenantUsageEventModel.recorded_at >= from_ts,
                    TenantUsageEventModel.recorded_at <= to_ts,
                )
                .group_by(TenantUsageEventModel.metric_code, TenantUsageEventModel.unit)
            )
            rows: dict[str, dict[str, Any]] = {}
            for row in result.all():
                rows[row.metric_code] = {
                    "metric_code": row.metric_code,
                    "unit": row.unit,
                    "total_quantity": float(row.total_quantity or 0.0),
                    "total_amount": float(row.total_amount or 0.0),
                    "event_count": int(row.event_count or 0),
                }
            return rows

    async def list_usage_events(
        self,
        organization_id: int,
        *,
        metric_code: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[TenantUsageEventModel], int]:
        async with self.async_session() as session:
            filters = [TenantUsageEventModel.organization_id == organization_id]
            if metric_code:
                filters.append(TenantUsageEventModel.metric_code == metric_code)
            if from_ts is not None:
                filters.append(TenantUsageEventModel.recorded_at >= from_ts)
            if to_ts is not None:
                filters.append(TenantUsageEventModel.recorded_at <= to_ts)

            base = select(TenantUsageEventModel).where(*filters)
            total = int(
                (await session.execute(select(func.count()).select_from(base.subquery())))
                .scalar_one()
                or 0
            )
            result = await session.execute(
                base.order_by(desc(TenantUsageEventModel.recorded_at))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all()), total

    async def upsert_quota(
        self,
        *,
        organization_id: int,
        metric_code: str,
        limit_quantity: float,
        period: str = "monthly",
        enforcement: str = "soft",
    ) -> TenantBillingQuotaModel:
        async with self.async_session() as session:
            stmt = (
                insert(TenantBillingQuotaModel)
                .values(
                    organization_id=organization_id,
                    metric_code=metric_code,
                    period=period,
                    limit_quantity=limit_quantity,
                    enforcement=enforcement,
                )
                .on_conflict_do_update(
                    index_elements=["organization_id", "metric_code", "period"],
                    set_={
                        "limit_quantity": limit_quantity,
                        "enforcement": enforcement,
                    },
                )
                .returning(TenantBillingQuotaModel)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.scalar_one()

    async def list_quotas(self, organization_id: int) -> list[TenantBillingQuotaModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(TenantBillingQuotaModel).where(
                    TenantBillingQuotaModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def get_quota(
        self,
        organization_id: int,
        metric_code: str,
        *,
        period: str = "monthly",
    ) -> TenantBillingQuotaModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(TenantBillingQuotaModel).where(
                    TenantBillingQuotaModel.organization_id == organization_id,
                    TenantBillingQuotaModel.metric_code == metric_code,
                    TenantBillingQuotaModel.period == period,
                )
            )
            return result.scalars().first()

    async def create_invoice(
        self,
        *,
        organization_id: int,
        invoice_number: str,
        period_start: datetime,
        period_end: datetime,
        currency: str,
        subtotal: float,
        tax_amount: float,
        total_amount: float,
        status: str = "draft",
        metadata: dict[str, Any] | None = None,
        line_items: list[dict[str, Any]],
        issued_at: datetime | None = None,
    ) -> TenantInvoiceModel:
        async with self.async_session() as session:
            invoice = TenantInvoiceModel(
                organization_id=organization_id,
                invoice_number=invoice_number,
                period_start=period_start,
                period_end=period_end,
                currency=currency,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_amount=total_amount,
                status=status,
                metadata_json=metadata or {},
                issued_at=issued_at,
            )
            session.add(invoice)
            await session.flush()
            for item in line_items:
                session.add(
                    TenantInvoiceLineModel(
                        invoice_id=invoice.id,
                        metric_code=item["metric_code"],
                        description=item["description"],
                        quantity=item["quantity"],
                        unit=item["unit"],
                        unit_price=item["unit_price"],
                        amount=item["amount"],
                        metadata_json=item.get("metadata") or {},
                    )
                )
            await session.commit()
            await session.refresh(invoice)
            return invoice

    async def list_invoices(
        self,
        organization_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TenantInvoiceModel], int]:
        async with self.async_session() as session:
            base = select(TenantInvoiceModel).where(
                TenantInvoiceModel.organization_id == organization_id
            )
            total = int(
                (await session.execute(select(func.count()).select_from(base.subquery())))
                .scalar_one()
                or 0
            )
            result = await session.execute(
                base.order_by(desc(TenantInvoiceModel.period_start))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all()), total

    async def get_invoice(
        self,
        invoice_id: int,
        *,
        organization_id: int,
    ) -> TenantInvoiceModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(TenantInvoiceModel)
                .options(selectinload(TenantInvoiceModel.line_items))
                .where(
                    TenantInvoiceModel.id == invoice_id,
                    TenantInvoiceModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def update_invoice_status(
        self,
        invoice_id: int,
        *,
        organization_id: int,
        status: str,
        issued_at: datetime | None = None,
    ) -> TenantInvoiceModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(TenantInvoiceModel)
                .where(
                    TenantInvoiceModel.id == invoice_id,
                    TenantInvoiceModel.organization_id == organization_id,
                )
                .with_for_update()
            )
            invoice = result.scalars().first()
            if not invoice:
                return None
            invoice.status = status
            if issued_at is not None:
                invoice.issued_at = issued_at
            await session.commit()
            await session.refresh(invoice)
            return invoice
