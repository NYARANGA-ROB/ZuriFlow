from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.db.base_client import BaseDBClient
from api.db.models import (
    CustomerAuditLogModel,
    CustomerCallHistoryModel,
    CustomerDebtAccountModel,
    CustomerEscalationHistoryModel,
    CustomerModel,
    CustomerPaymentModel,
)
from api.services.kenya.phone import normalize_kenyan_phone
from api.utils.telephony_address import normalize_telephony_address


def _phone_canonical(phone_e164: str) -> str:
    kenya = normalize_kenyan_phone(phone_e164)
    if kenya.valid and kenya.e164:
        return kenya.e164
    return normalize_telephony_address(phone_e164, country_hint="KE").canonical


def _phone_original(phone_e164: str) -> str:
    kenya = normalize_kenyan_phone(phone_e164)
    return kenya.original if kenya.original else phone_e164


class CrmClient(BaseDBClient):
    # --- Customers ---

    async def create_customer(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        full_name: str,
        email: str | None = None,
        preferred_locale: str = "mixed",
        secondary_locales: list[str] | None = None,
        external_crm_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerModel:
        async with self.async_session() as session:
            customer = CustomerModel(
                organization_id=organization_id,
                phone_e164=_phone_canonical(phone_e164),
                phone_original=_phone_original(phone_e164),
                full_name=full_name,
                email=email,
                preferred_locale=preferred_locale,
                secondary_locales=secondary_locales or [],
                external_crm_id=external_crm_id,
                metadata_json=metadata or {},
            )
            session.add(customer)
            await session.commit()
            await session.refresh(customer)
            return customer

    async def get_customer(
        self,
        customer_id: int,
        *,
        organization_id: int,
    ) -> CustomerModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerModel)
                .where(CustomerModel.id == customer_id)
                .where(CustomerModel.organization_id == organization_id)
            )
            return result.scalars().first()

    async def get_customer_by_phone(
        self,
        *,
        organization_id: int,
        phone_e164: str,
    ) -> CustomerModel | None:
        phone = _phone_canonical(phone_e164)
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerModel)
                .where(CustomerModel.organization_id == organization_id)
                .where(CustomerModel.phone_e164 == phone)
            )
            return result.scalars().first()

    async def get_customer_by_uuid(
        self,
        customer_uuid: str,
        *,
        organization_id: int,
    ) -> CustomerModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerModel)
                .where(CustomerModel.customer_uuid == customer_uuid)
                .where(CustomerModel.organization_id == organization_id)
            )
            return result.scalars().first()

    async def list_customers(
        self,
        *,
        organization_id: int,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[CustomerModel]:
        async with self.async_session() as session:
            query = select(CustomerModel).where(
                CustomerModel.organization_id == organization_id
            )
            if active_only:
                query = query.where(CustomerModel.is_active.is_(True))
            if search:
                pattern = f"%{search}%"
                query = query.where(
                    (CustomerModel.full_name.ilike(pattern))
                    | (CustomerModel.phone_e164.ilike(pattern))
                    | (CustomerModel.email.ilike(pattern))
                )
            query = query.order_by(desc(CustomerModel.updated_at)).limit(limit).offset(offset)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_customer(
        self,
        customer_id: int,
        *,
        organization_id: int,
        **fields: Any,
    ) -> CustomerModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerModel)
                .where(CustomerModel.id == customer_id)
                .where(CustomerModel.organization_id == organization_id)
            )
            customer = result.scalars().first()
            if not customer:
                return None
            for key, value in fields.items():
                if key == "metadata" and value is not None:
                    customer.metadata_json = {**(customer.metadata_json or {}), **value}
                elif key == "phone_e164" and value is not None:
                    customer.phone_e164 = _phone_canonical(value)
                elif hasattr(customer, key) and value is not None:
                    setattr(customer, key, value)
            customer.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(customer)
            return customer

    async def get_customer_profile_bundle(
        self,
        customer_id: int,
        *,
        organization_id: int,
        history_limit: int = 20,
    ) -> CustomerModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerModel)
                .options(
                    selectinload(CustomerModel.debt_accounts),
                    selectinload(CustomerModel.payments),
                    selectinload(CustomerModel.call_history),
                    selectinload(CustomerModel.escalations),
                )
                .where(CustomerModel.id == customer_id)
                .where(CustomerModel.organization_id == organization_id)
            )
            customer = result.scalars().first()
            if customer is None:
                return None
            customer.payments = sorted(
                customer.payments,
                key=lambda p: p.paid_at or p.created_at or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )[:history_limit]
            customer.call_history = sorted(
                customer.call_history,
                key=lambda c: c.started_at or c.created_at or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )[:history_limit]
            customer.escalations = sorted(
                customer.escalations,
                key=lambda e: e.created_at or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )[:history_limit]
            return customer

    # --- Debt accounts ---

    async def upsert_debt_account(
        self,
        *,
        customer_id: int,
        organization_id: int,
        account_reference: str,
        outstanding_balance: float,
        currency: str = "KES",
        days_past_due: int = 0,
        minimum_settlement: float | None = None,
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> CustomerDebtAccountModel:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerDebtAccountModel)
                .where(CustomerDebtAccountModel.organization_id == organization_id)
                .where(CustomerDebtAccountModel.account_reference == account_reference)
            )
            account = result.scalars().first()
            if account is None:
                account = CustomerDebtAccountModel(
                    customer_id=customer_id,
                    organization_id=organization_id,
                    account_reference=account_reference,
                    outstanding_balance=outstanding_balance,
                    currency=currency,
                    days_past_due=days_past_due,
                    minimum_settlement=minimum_settlement,
                    status=status,
                    metadata_json=metadata or {},
                )
                session.add(account)
            else:
                account.outstanding_balance = outstanding_balance
                account.days_past_due = days_past_due
                account.minimum_settlement = minimum_settlement
                account.status = status
                if metadata:
                    account.metadata_json = {**(account.metadata_json or {}), **metadata}
                account.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(account)
            return account

    async def list_debt_accounts(
        self,
        *,
        customer_id: int,
        organization_id: int,
    ) -> list[CustomerDebtAccountModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerDebtAccountModel)
                .where(CustomerDebtAccountModel.customer_id == customer_id)
                .where(CustomerDebtAccountModel.organization_id == organization_id)
                .order_by(desc(CustomerDebtAccountModel.updated_at))
            )
            return list(result.scalars().all())

    # --- Payments ---

    async def get_payment_by_mpesa_transaction_id(
        self,
        mpesa_transaction_id: int,
        *,
        organization_id: int,
    ) -> CustomerPaymentModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerPaymentModel).where(
                    CustomerPaymentModel.organization_id == organization_id,
                    CustomerPaymentModel.mpesa_transaction_id == mpesa_transaction_id,
                )
            )
            return result.scalars().first()

    async def record_payment(
        self,
        *,
        customer_id: int,
        organization_id: int,
        amount: float,
        currency: str = "KES",
        payment_method: str = "mpesa",
        status: str = "success",
        debt_account_id: int | None = None,
        mpesa_transaction_id: int | None = None,
        workflow_run_id: int | None = None,
        receipt_reference: str | None = None,
        paid_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerPaymentModel:
        async with self.async_session() as session:
            payment = CustomerPaymentModel(
                customer_id=customer_id,
                organization_id=organization_id,
                amount=amount,
                currency=currency,
                payment_method=payment_method,
                status=status,
                debt_account_id=debt_account_id,
                mpesa_transaction_id=mpesa_transaction_id,
                workflow_run_id=workflow_run_id,
                receipt_reference=receipt_reference,
                paid_at=paid_at or datetime.now(UTC),
                metadata_json=metadata or {},
            )
            session.add(payment)
            if debt_account_id and status == "success":
                acc_result = await session.execute(
                    select(CustomerDebtAccountModel).where(
                        CustomerDebtAccountModel.id == debt_account_id
                    )
                )
                account = acc_result.scalars().first()
                if account:
                    account.outstanding_balance = max(0.0, account.outstanding_balance - amount)
                    account.last_payment_at = paid_at or datetime.now(UTC)
                    if account.outstanding_balance <= 0:
                        account.status = "settled"
            await session.commit()
            await session.refresh(payment)
            return payment

    async def list_payments(
        self,
        *,
        customer_id: int,
        organization_id: int,
        limit: int = 50,
    ) -> list[CustomerPaymentModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerPaymentModel)
                .where(CustomerPaymentModel.customer_id == customer_id)
                .where(CustomerPaymentModel.organization_id == organization_id)
                .order_by(desc(CustomerPaymentModel.paid_at), desc(CustomerPaymentModel.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    # --- Call history ---

    async def record_call(
        self,
        *,
        customer_id: int,
        organization_id: int,
        phone_e164: str,
        call_type: str = "outbound",
        workflow_run_id: int | None = None,
        duration_s: float | None = None,
        disposition: str | None = None,
        outcome: str | None = None,
        summary: str | None = None,
        language: str = "mixed",
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerCallHistoryModel:
        async with self.async_session() as session:
            call = CustomerCallHistoryModel(
                customer_id=customer_id,
                organization_id=organization_id,
                phone_e164=_phone_canonical(phone_e164),
                call_type=call_type,
                workflow_run_id=workflow_run_id,
                duration_s=duration_s,
                disposition=disposition,
                outcome=outcome,
                summary=summary,
                language=language,
                started_at=started_at,
                ended_at=ended_at,
                metadata_json=metadata or {},
            )
            session.add(call)
            await session.commit()
            await session.refresh(call)
            return call

    # --- Escalations ---

    async def record_escalation(
        self,
        *,
        customer_id: int,
        organization_id: int,
        reason: str,
        risk_level: str = "medium",
        workflow_run_id: int | None = None,
        session_id: str | None = None,
        queue_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerEscalationHistoryModel:
        async with self.async_session() as session:
            row = CustomerEscalationHistoryModel(
                customer_id=customer_id,
                organization_id=organization_id,
                reason=reason,
                risk_level=risk_level,
                workflow_run_id=workflow_run_id,
                session_id=session_id,
                queue_name=queue_name,
                metadata_json=metadata or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def resolve_escalation(
        self,
        escalation_id: int,
        *,
        organization_id: int,
    ) -> CustomerEscalationHistoryModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerEscalationHistoryModel)
                .where(CustomerEscalationHistoryModel.id == escalation_id)
                .where(CustomerEscalationHistoryModel.organization_id == organization_id)
            )
            row = result.scalars().first()
            if not row:
                return None
            row.resolved = True
            row.resolved_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return row

    # --- Audit ---

    async def append_audit_log(
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
    ) -> CustomerAuditLogModel:
        async with self.async_session() as session:
            log = CustomerAuditLogModel(
                organization_id=organization_id,
                customer_id=customer_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                changes=changes or {},
                ip_address=ip_address,
                metadata_json=metadata or {},
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return log

    async def list_audit_logs(
        self,
        *,
        organization_id: int,
        customer_id: int | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[CustomerAuditLogModel]:
        async with self.async_session() as session:
            query = select(CustomerAuditLogModel).where(
                CustomerAuditLogModel.organization_id == organization_id
            )
            if customer_id is not None:
                query = query.where(CustomerAuditLogModel.customer_id == customer_id)
            if action:
                query = query.where(CustomerAuditLogModel.action == action)
            query = query.order_by(desc(CustomerAuditLogModel.created_at)).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def customer_total_outstanding(
        self,
        *,
        customer_id: int,
        organization_id: int,
    ) -> float:
        async with self.async_session() as session:
            result = await session.execute(
                select(func.coalesce(func.sum(CustomerDebtAccountModel.outstanding_balance), 0.0))
                .where(CustomerDebtAccountModel.customer_id == customer_id)
                .where(CustomerDebtAccountModel.organization_id == organization_id)
                .where(CustomerDebtAccountModel.status == "active")
            )
            return float(result.scalar() or 0.0)
