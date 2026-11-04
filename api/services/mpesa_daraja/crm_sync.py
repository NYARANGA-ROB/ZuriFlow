"""Sync completed M-Pesa transactions into CRM payment history."""

from __future__ import annotations

from loguru import logger

from api.constants import CRM_ENABLED
from api.db import db_client
from api.services.crm.service import get_customer_service
from api.services.mpesa_daraja.types import MpesaTransactionStatus


async def sync_completed_transaction_to_crm(
    transaction_id: int,
    *,
    organization_id: int,
) -> bool:
    """Record a successful M-Pesa payment against the CRM customer profile."""
    if not CRM_ENABLED:
        return False

    tx = await db_client.get_transaction(transaction_id, organization_id=organization_id)
    if not tx or tx.status != MpesaTransactionStatus.COMPLETED.value:
        return False

    existing = await db_client.get_payment_by_mpesa_transaction_id(
        transaction_id, organization_id=organization_id
    )
    if existing:
        return False

    metadata = tx.metadata_json or {}
    customer_id = metadata.get("customer_id")

    if not customer_id:
        customer = await db_client.get_customer_by_phone(
            organization_id=organization_id,
            phone_e164=tx.phone_e164,
        )
        if not customer:
            logger.debug(
                "M-Pesa CRM sync skipped — no customer for phone org={} tx={}",
                organization_id,
                transaction_id,
            )
            return False
        customer_id = customer.id

    debt_account_id = metadata.get("debt_account_id")
    svc = get_customer_service()
    if not svc.enabled:
        return False

    await svc.record_payment(
        int(customer_id),
        organization_id=organization_id,
        amount=float(tx.amount),
        currency=tx.currency or "KES",
        payment_method="mpesa",
        status="success",
        debt_account_id=int(debt_account_id) if debt_account_id else None,
        mpesa_transaction_id=transaction_id,
        workflow_run_id=tx.workflow_run_id,
        receipt_reference=tx.mpesa_receipt_number,
        metadata={"account_reference": tx.account_reference},
    )
    logger.info(
        "Synced M-Pesa transaction {} to CRM customer {} (org {})",
        transaction_id,
        customer_id,
        organization_id,
    )
    return True
