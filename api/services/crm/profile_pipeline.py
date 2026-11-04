"""Profile retrieval pipeline — assembles full customer CRM view."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.db.models import CustomerModel
from api.services.crm.audit import get_crm_audit_logger
from api.services.crm.types import CustomerProfile


def _dt_iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _serialize_debt(account) -> dict[str, Any]:
    return {
        "id": account.id,
        "account_reference": account.account_reference,
        "outstanding_balance": account.outstanding_balance,
        "currency": account.currency,
        "days_past_due": account.days_past_due,
        "minimum_settlement": account.minimum_settlement,
        "status": account.status,
        "last_payment_at": _dt_iso(account.last_payment_at),
        "metadata": account.metadata_json or {},
    }


def _serialize_payment(payment) -> dict[str, Any]:
    return {
        "id": payment.id,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_method": payment.payment_method,
        "status": payment.status,
        "receipt_reference": payment.receipt_reference,
        "paid_at": _dt_iso(payment.paid_at),
        "debt_account_id": payment.debt_account_id,
        "mpesa_transaction_id": payment.mpesa_transaction_id,
        "workflow_run_id": payment.workflow_run_id,
        "metadata": payment.metadata_json or {},
    }


def _serialize_call(call) -> dict[str, Any]:
    return {
        "id": call.id,
        "call_type": call.call_type,
        "phone_e164": call.phone_e164,
        "duration_s": call.duration_s,
        "disposition": call.disposition,
        "outcome": call.outcome,
        "summary": call.summary,
        "language": call.language,
        "workflow_run_id": call.workflow_run_id,
        "started_at": _dt_iso(call.started_at),
        "ended_at": _dt_iso(call.ended_at),
        "metadata": call.metadata_json or {},
    }


def _serialize_escalation(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "reason": row.reason,
        "risk_level": row.risk_level,
        "queue_name": row.queue_name,
        "resolved": row.resolved,
        "resolved_at": _dt_iso(row.resolved_at),
        "session_id": row.session_id,
        "workflow_run_id": row.workflow_run_id,
        "created_at": _dt_iso(row.created_at),
        "metadata": row.metadata_json or {},
    }


class CustomerProfilePipeline:
    """Load and assemble customer profiles with related history."""

    def __init__(self) -> None:
        self._audit = get_crm_audit_logger()

    async def retrieve_by_id(
        self,
        customer_id: int,
        *,
        organization_id: int,
        actor_user_id: int | None = None,
        history_limit: int = 20,
        audit: bool = True,
    ) -> CustomerProfile | None:
        customer = await db_client.get_customer_profile_bundle(
            customer_id,
            organization_id=organization_id,
            history_limit=history_limit,
        )
        if customer is None:
            return None
        profile = await self._build_profile(customer, organization_id)
        if audit:
            await self._audit.log(
                organization_id=organization_id,
                action="profile_viewed",
                resource_type="customer",
                customer_id=customer_id,
                actor_user_id=actor_user_id,
                resource_id=str(customer_id),
            )
        return profile

    async def retrieve_by_phone(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        actor_user_id: int | None = None,
        history_limit: int = 20,
    ) -> CustomerProfile | None:
        customer = await db_client.get_customer_by_phone(
            organization_id=organization_id,
            phone_e164=phone_e164,
        )
        if customer is None:
            return None
        return await self.retrieve_by_id(
            customer.id,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            history_limit=history_limit,
        )

    async def _build_profile(
        self,
        customer: CustomerModel,
        organization_id: int,
    ) -> CustomerProfile:
        total = await db_client.customer_total_outstanding(
            customer_id=customer.id,
            organization_id=organization_id,
        )
        return CustomerProfile(
            id=customer.id,
            customer_uuid=customer.customer_uuid,
            organization_id=customer.organization_id,
            phone_e164=customer.phone_e164,
            full_name=customer.full_name,
            email=customer.email,
            preferred_locale=customer.preferred_locale,
            secondary_locales=list(customer.secondary_locales or []),
            external_crm_id=customer.external_crm_id,
            is_active=customer.is_active,
            total_outstanding=total,
            debt_accounts=[_serialize_debt(a) for a in customer.debt_accounts],
            payment_history=[_serialize_payment(p) for p in customer.payments],
            call_history=[_serialize_call(c) for c in customer.call_history],
            escalation_history=[_serialize_escalation(e) for e in customer.escalations],
            metadata={
                **(customer.metadata_json or {}),
                "phone_original": getattr(customer, "phone_original", None),
            },
            created_at=_dt_iso(customer.created_at),
            updated_at=_dt_iso(customer.updated_at),
        )


_pipeline: CustomerProfilePipeline | None = None


def get_customer_profile_pipeline() -> CustomerProfilePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = CustomerProfilePipeline()
    return _pipeline
