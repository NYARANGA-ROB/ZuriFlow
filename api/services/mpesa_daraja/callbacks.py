from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client
from api.services.mpesa_daraja.config import ORG_CONFIG_KEY, MpesaDarajaConfig
from api.services.mpesa_daraja.types import (
    MpesaEventType,
    MpesaTransactionStatus,
    STKCallbackResult,
)
from api.services.mpesa_daraja.verification import TransactionVerificationService
from api.services.mpesa_daraja.webhook import parse_stk_callback


class MpesaCallbackProcessor:
    """Process Safaricom STK callbacks asynchronously with idempotency."""

    def __init__(self) -> None:
        self._verification = TransactionVerificationService()

    async def load_org_config(self, organization_id: int) -> MpesaDarajaConfig:
        row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
        return MpesaDarajaConfig.from_dict(row.value if row else None)

    async def process_stk_callback(
        self,
        *,
        organization_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        parsed = parse_stk_callback(payload)
        tx = await db_client.get_transaction_by_checkout_request_id(
            parsed.checkout_request_id,
            organization_id=organization_id,
        )
        if not tx:
            logger.warning(
                "STK callback for unknown checkout_request_id={} org={}",
                parsed.checkout_request_id,
                organization_id,
            )
            return {"success": False, "error": "transaction_not_found"}

        await db_client.append_event(
            transaction_id=tx.id,
            event_type=MpesaEventType.CALLBACK_RECEIVED.value,
            payload=payload,
        )

        if tx.status in {
            MpesaTransactionStatus.COMPLETED.value,
            MpesaTransactionStatus.FAILED.value,
            MpesaTransactionStatus.CANCELLED.value,
        }:
            return {
                "success": True,
                "transaction_id": tx.id,
                "status": tx.status,
                "idempotent": True,
            }

        result = await self._apply_callback(tx.id, organization_id, parsed)
        await db_client.append_event(
            transaction_id=tx.id,
            event_type=MpesaEventType.CALLBACK_PROCESSED.value,
            payload=result,
        )
        return result

    async def _apply_callback(
        self,
        transaction_id: int,
        organization_id: int,
        parsed: STKCallbackResult,
    ) -> dict[str, Any]:
        if parsed.is_success:
            await db_client.update_transaction(
                transaction_id,
                organization_id=organization_id,
                status=MpesaTransactionStatus.COMPLETED.value,
                result_code=parsed.result_code,
                result_desc=parsed.result_desc,
                merchant_request_id=parsed.merchant_request_id,
                mpesa_receipt_number=parsed.mpesa_receipt_number,
                callback_payload=parsed.raw_payload,
                metadata={
                    "phone_number": parsed.phone_number,
                    "transaction_date": parsed.transaction_date,
                    "callback_metadata": parsed.metadata_items,
                },
            )
            await self._notify_workflow_run(
                transaction_id=transaction_id,
                organization_id=organization_id,
                status=MpesaTransactionStatus.COMPLETED.value,
                receipt=parsed.mpesa_receipt_number,
            )
            await self._notify_voice_workflow(
                transaction_id=transaction_id,
                organization_id=organization_id,
            )
            try:
                from api.services.mpesa_daraja.crm_sync import (
                    sync_completed_transaction_to_crm,
                )

                await sync_completed_transaction_to_crm(
                    transaction_id, organization_id=organization_id
                )
            except Exception as e:
                logger.debug("M-Pesa CRM sync skipped for tx {}: {}", transaction_id, e)
            try:
                from api.services.platform_events.adapters import publish_payment_completed

                tx = await db_client.get_transaction(
                    transaction_id, organization_id=organization_id
                )
                await publish_payment_completed(
                    organization_id=organization_id,
                    transaction_id=transaction_id,
                    workflow_run_id=tx.workflow_run_id if tx else None,
                    mpesa_receipt_number=parsed.mpesa_receipt_number,
                )
            except Exception as exc:
                logger.debug("platform payment.completed publish skipped: {}", exc)
            return {
                "success": True,
                "transaction_id": transaction_id,
                "status": MpesaTransactionStatus.COMPLETED.value,
                "mpesa_receipt_number": parsed.mpesa_receipt_number,
            }

        status = MpesaTransactionStatus.FAILED.value
        if parsed.result_code == 1032:
            status = MpesaTransactionStatus.CANCELLED.value

        await db_client.update_transaction(
            transaction_id,
            organization_id=organization_id,
            status=status,
            result_code=parsed.result_code,
            result_desc=parsed.result_desc,
            merchant_request_id=parsed.merchant_request_id,
            callback_payload=parsed.raw_payload,
        )
        await self._notify_workflow_run(
            transaction_id=transaction_id,
            organization_id=organization_id,
            status=status,
            receipt=None,
        )
        await self._notify_voice_workflow(
            transaction_id=transaction_id,
            organization_id=organization_id,
        )
        try:
            from api.services.platform_events.adapters import publish_payment_failed

            tx = await db_client.get_transaction(
                transaction_id, organization_id=organization_id
            )
            await publish_payment_failed(
                organization_id=organization_id,
                transaction_id=transaction_id,
                workflow_run_id=tx.workflow_run_id if tx else None,
                reason=parsed.result_desc,
            )
        except Exception as exc:
            logger.debug("platform payment.failed publish skipped: {}", exc)
        return {
            "success": True,
            "transaction_id": transaction_id,
            "status": status,
            "result_code": parsed.result_code,
            "result_desc": parsed.result_desc,
        }

    async def _notify_workflow_run(
        self,
        *,
        transaction_id: int,
        organization_id: int,
        status: str,
        receipt: str | None,
    ) -> None:
        tx = await db_client.get_transaction(transaction_id, organization_id=organization_id)
        if not tx or not tx.workflow_run_id:
            return
        await db_client.update_workflow_run(
            run_id=tx.workflow_run_id,
            gathered_context={
                "mpesa_payment": {
                    "transaction_id": transaction_id,
                    "status": status,
                    "mpesa_receipt_number": receipt,
                    "amount": tx.amount,
                    "phone_e164": tx.phone_e164,
                },
                "payment_url": None,
            },
        )

    async def _notify_voice_workflow(
        self,
        *,
        transaction_id: int,
        organization_id: int,
    ) -> None:
        tx = await db_client.get_transaction(transaction_id, organization_id=organization_id)
        if not tx:
            return
        metadata = tx.metadata_json or {}
        if not metadata.get("voice_session_id"):
            return
        from api.tasks.arq import enqueue_job
        from api.tasks.function_names import FunctionNames

        await enqueue_job(
            FunctionNames.VOICE_MPESA_COMPLETE_PAYMENT,
            transaction_id,
            organization_id,
        )
