"""Customer CRM service layer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from api.constants import CRM_ENABLED
from api.db import db_client
from api.services.crm.audit import get_crm_audit_logger
from api.services.crm.profile_pipeline import get_customer_profile_pipeline
from api.services.crm.types import CustomerProfile


class CustomerService:
    """Business logic for customer records and CRM integrations."""

    def __init__(self) -> None:
        self._audit = get_crm_audit_logger()
        self._profiles = get_customer_profile_pipeline()

    @property
    def enabled(self) -> bool:
        return CRM_ENABLED

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
        actor_user_id: int | None = None,
        debt_account: dict[str, Any] | None = None,
    ) -> CustomerProfile:
        existing = await db_client.get_customer_by_phone(
            organization_id=organization_id,
            phone_e164=phone_e164,
        )
        if existing:
            return await self._profiles.retrieve_by_id(
                existing.id,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
            )

        customer = await db_client.create_customer(
            organization_id=organization_id,
            phone_e164=phone_e164,
            full_name=full_name,
            email=email,
            preferred_locale=preferred_locale,
            secondary_locales=secondary_locales,
            external_crm_id=external_crm_id,
            metadata=metadata,
        )

        if debt_account:
            await db_client.upsert_debt_account(
                customer_id=customer.id,
                organization_id=organization_id,
                account_reference=debt_account["account_reference"],
                outstanding_balance=float(debt_account["outstanding_balance"]),
                currency=debt_account.get("currency", "KES"),
                days_past_due=int(debt_account.get("days_past_due", 0)),
                minimum_settlement=debt_account.get("minimum_settlement"),
                metadata=debt_account.get("metadata"),
            )

        await self._audit.log(
            organization_id=organization_id,
            action="customer_created",
            resource_type="customer",
            customer_id=customer.id,
            actor_user_id=actor_user_id,
            resource_id=str(customer.id),
            changes={"phone_e164": customer.phone_e164, "full_name": full_name},
        )

        profile = await self._profiles.retrieve_by_id(
            customer.id,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            audit=False,
        )
        return profile  # type: ignore[return-value]

    async def update_customer(
        self,
        customer_id: int,
        *,
        organization_id: int,
        actor_user_id: int | None = None,
        **fields: Any,
    ) -> CustomerProfile | None:
        customer = await db_client.update_customer(
            customer_id,
            organization_id=organization_id,
            **fields,
        )
        if not customer:
            return None
        await self._audit.log(
            organization_id=organization_id,
            action="customer_updated",
            resource_type="customer",
            customer_id=customer_id,
            actor_user_id=actor_user_id,
            resource_id=str(customer_id),
            changes={k: v for k, v in fields.items() if v is not None},
        )
        return await self._profiles.retrieve_by_id(
            customer_id,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            audit=False,
        )

    async def get_profile(
        self,
        customer_id: int,
        *,
        organization_id: int,
        actor_user_id: int | None = None,
    ) -> CustomerProfile | None:
        return await self._profiles.retrieve_by_id(
            customer_id,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
        )

    async def get_profile_by_phone(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        actor_user_id: int | None = None,
    ) -> CustomerProfile | None:
        return await self._profiles.retrieve_by_phone(
            organization_id=organization_id,
            phone_e164=phone_e164,
            actor_user_id=actor_user_id,
        )

    async def list_customers(
        self,
        *,
        organization_id: int,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = await db_client.list_customers(
            organization_id=organization_id,
            search=search,
            limit=limit,
            offset=offset,
        )
        return [
            {
                "id": c.id,
                "customer_uuid": c.customer_uuid,
                "full_name": c.full_name,
                "phone_e164": c.phone_e164,
                "preferred_locale": c.preferred_locale,
                "is_active": c.is_active,
            }
            for c in rows
        ]

    async def upsert_debt_account(
        self,
        customer_id: int,
        *,
        organization_id: int,
        account_reference: str,
        outstanding_balance: float,
        actor_user_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        account = await db_client.upsert_debt_account(
            customer_id=customer_id,
            organization_id=organization_id,
            account_reference=account_reference,
            outstanding_balance=outstanding_balance,
            currency=kwargs.get("currency", "KES"),
            days_past_due=int(kwargs.get("days_past_due", 0)),
            minimum_settlement=kwargs.get("minimum_settlement"),
            status=kwargs.get("status", "active"),
            metadata=kwargs.get("metadata"),
        )
        await self._audit.log(
            organization_id=organization_id,
            action="debt_account_upserted",
            resource_type="debt_account",
            customer_id=customer_id,
            actor_user_id=actor_user_id,
            resource_id=str(account.id),
            changes={"outstanding_balance": outstanding_balance},
        )
        return {
            "id": account.id,
            "account_reference": account.account_reference,
            "outstanding_balance": account.outstanding_balance,
            "status": account.status,
        }

    async def record_payment(
        self,
        customer_id: int,
        *,
        organization_id: int,
        amount: float,
        actor_user_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payment = await db_client.record_payment(
            customer_id=customer_id,
            organization_id=organization_id,
            amount=amount,
            currency=kwargs.get("currency", "KES"),
            payment_method=kwargs.get("payment_method", "mpesa"),
            status=kwargs.get("status", "success"),
            debt_account_id=kwargs.get("debt_account_id"),
            mpesa_transaction_id=kwargs.get("mpesa_transaction_id"),
            workflow_run_id=kwargs.get("workflow_run_id"),
            receipt_reference=kwargs.get("receipt_reference"),
            paid_at=kwargs.get("paid_at"),
            metadata=kwargs.get("metadata"),
        )
        await self._audit.log(
            organization_id=organization_id,
            action="payment_recorded",
            resource_type="payment",
            customer_id=customer_id,
            actor_user_id=actor_user_id,
            resource_id=str(payment.id),
            changes={"amount": amount, "status": payment.status},
        )
        return {
            "id": payment.id,
            "amount": payment.amount,
            "status": payment.status,
            "receipt_reference": payment.receipt_reference,
        }

    async def record_call(
        self,
        customer_id: int,
        *,
        organization_id: int,
        phone_e164: str,
        actor_user_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        call = await db_client.record_call(
            customer_id=customer_id,
            organization_id=organization_id,
            phone_e164=phone_e164,
            call_type=kwargs.get("call_type", "outbound"),
            workflow_run_id=kwargs.get("workflow_run_id"),
            duration_s=kwargs.get("duration_s"),
            disposition=kwargs.get("disposition"),
            outcome=kwargs.get("outcome"),
            summary=kwargs.get("summary"),
            language=kwargs.get("language", "mixed"),
            started_at=kwargs.get("started_at"),
            ended_at=kwargs.get("ended_at"),
            metadata=kwargs.get("metadata"),
        )
        await self._audit.log(
            organization_id=organization_id,
            action="call_recorded",
            resource_type="call",
            customer_id=customer_id,
            actor_user_id=actor_user_id,
            resource_id=str(call.id),
            changes={"outcome": call.outcome, "disposition": call.disposition},
        )
        return {"id": call.id, "outcome": call.outcome}

    async def record_escalation(
        self,
        customer_id: int,
        *,
        organization_id: int,
        reason: str,
        actor_user_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        row = await db_client.record_escalation(
            customer_id=customer_id,
            organization_id=organization_id,
            reason=reason,
            risk_level=kwargs.get("risk_level", "medium"),
            workflow_run_id=kwargs.get("workflow_run_id"),
            session_id=kwargs.get("session_id"),
            queue_name=kwargs.get("queue_name"),
            metadata=kwargs.get("metadata"),
        )
        await self._audit.log(
            organization_id=organization_id,
            action="escalation_recorded",
            resource_type="escalation",
            customer_id=customer_id,
            actor_user_id=actor_user_id,
            resource_id=str(row.id),
            changes={"reason": reason, "risk_level": row.risk_level},
        )
        return {"id": row.id, "reason": row.reason, "risk_level": row.risk_level}

    async def list_audit_logs(
        self,
        *,
        organization_id: int,
        customer_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        rows = await db_client.list_audit_logs(
            organization_id=organization_id,
            customer_id=customer_id,
            limit=limit,
        )
        return [
            {
                "id": r.id,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "customer_id": r.customer_id,
                "actor_user_id": r.actor_user_id,
                "changes": r.changes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def sync_from_debt_collection(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        full_name: str,
        account_reference: str,
        outstanding_balance: float,
        days_past_due: int = 0,
        preferred_locale: str = "mixed",
        workflow_run_id: int | None = None,
    ) -> CustomerProfile:
        """Ensure CRM customer exists for a debt collection session."""
        profile = await self.get_profile_by_phone(
            organization_id=organization_id,
            phone_e164=phone_e164,
        )
        if profile is None:
            profile = await self.create_customer(
                organization_id=organization_id,
                phone_e164=phone_e164,
                full_name=full_name,
                preferred_locale=preferred_locale,
                debt_account={
                    "account_reference": account_reference,
                    "outstanding_balance": outstanding_balance,
                    "days_past_due": days_past_due,
                },
            )
        else:
            await self.upsert_debt_account(
                profile.id,
                organization_id=organization_id,
                account_reference=account_reference,
                outstanding_balance=outstanding_balance,
                days_past_due=days_past_due,
            )
            profile = await self.get_profile(profile.id, organization_id=organization_id)

        if workflow_run_id:
            await self.record_call(
                profile.id,
                organization_id=organization_id,
                phone_e164=phone_e164,
                call_type="outbound",
                workflow_run_id=workflow_run_id,
                outcome="debt_collection_started",
                started_at=datetime.now(UTC),
            )
        return profile  # type: ignore[return-value]


_service: CustomerService | None = None


def get_customer_service() -> CustomerService:
    global _service
    if _service is None:
        _service = CustomerService()
    return _service
