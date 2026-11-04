"""Integration hooks for usage collectors."""

from __future__ import annotations

from api.constants import TENANT_USAGE_BILLING_ENABLED
from api.db.models import MpesaTransactionModel, WhatsAppMessageModel
from api.services.tenant_billing.service import get_tenant_billing_service


async def on_workflow_run_completed(workflow_run_id: int) -> None:
    if not TENANT_USAGE_BILLING_ENABLED:
        return
    await get_tenant_billing_service().collect_workflow_run(workflow_run_id)


async def on_whatsapp_message_recorded(
    *, organization_id: int, message: WhatsAppMessageModel
) -> None:
    if not TENANT_USAGE_BILLING_ENABLED:
        return
    await get_tenant_billing_service().collect_whatsapp_message(
        organization_id=organization_id, message=message
    )


async def on_mpesa_transaction_updated(tx: MpesaTransactionModel) -> None:
    if not TENANT_USAGE_BILLING_ENABLED:
        return
    await get_tenant_billing_service().collect_mpesa_transaction(tx)
