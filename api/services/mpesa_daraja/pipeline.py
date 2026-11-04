from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from api.constants import KENYA_PRODUCTION_MODE, MPESA_STK_QUERY_DELAY_S, MPESA_STK_QUERY_DELAY_S_PROD
from api.db import db_client
from api.services.mpesa_daraja.callbacks import MpesaCallbackProcessor
from api.services.mpesa_daraja.client import DarajaClient
from api.services.mpesa_daraja.config import ORG_CONFIG_KEY, MpesaDarajaConfig
from api.services.org_config_cache import mpesa_config_cache
from api.services.mpesa_daraja.types import (
    MpesaEventType,
    MpesaTransactionStatus,
    STKPushRequest,
    STKPushResponse,
)
from api.services.mpesa_daraja.verification import TransactionVerificationService
from api.tasks.function_names import FunctionNames
from api.utils.telephony_address import normalize_telephony_address


class STKPushService:
    """Initiate and track M-Pesa STK Push payments."""

    def __init__(self) -> None:
        self._verification = TransactionVerificationService()
        self._callbacks = MpesaCallbackProcessor()

    async def load_org_config(self, organization_id: int) -> MpesaDarajaConfig:
        cache = mpesa_config_cache()
        cached = cache.get(organization_id, ORG_CONFIG_KEY)
        if cached is not None:
            return cached
        row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
        config = MpesaDarajaConfig.from_dict(row.value if row else None)
        cache.set(organization_id, ORG_CONFIG_KEY, config)
        return config

    async def initiate_stk_push(self, request: STKPushRequest) -> STKPushResponse:
        config = await self.load_org_config(request.organization_id)
        validation_error = config.validate_for_stk()
        if validation_error:
            return STKPushResponse(success=False, error=validation_error)

        phone = normalize_telephony_address(request.phone_e164)
        tx = await db_client.create_transaction(
            organization_id=request.organization_id,
            phone_e164=phone,
            amount=request.amount,
            account_reference=request.account_reference,
            transaction_desc=request.transaction_desc,
            workflow_run_id=request.workflow_run_id,
            metadata=request.metadata,
        )
        await db_client.append_event(
            transaction_id=tx.id,
            event_type=MpesaEventType.CREATED.value,
            payload={"amount": request.amount, "phone_e164": phone},
        )

        callback_url = f"{config.callback_base_url.rstrip('/')}/stk/{request.organization_id}"
        client = DarajaClient(config)

        try:
            raw = await client.stk_push(
                phone_e164=phone,
                amount=request.amount,
                account_reference=request.account_reference,
                transaction_desc=request.transaction_desc,
                callback_url=callback_url,
            )
        except Exception as exc:
            await db_client.update_transaction(
                tx.id,
                organization_id=request.organization_id,
                status=MpesaTransactionStatus.FAILED.value,
                result_desc=str(exc),
            )
            await db_client.append_event(
                transaction_id=tx.id,
                event_type=MpesaEventType.STK_INIT_FAILED.value,
                payload={"error": str(exc)},
            )
            return STKPushResponse(success=False, transaction_id=tx.id, error=str(exc))

        response_code = str(raw.get("ResponseCode", ""))
        if response_code != "0":
            error = raw.get("ResponseDescription") or raw.get("errorMessage") or str(raw)
            await db_client.update_transaction(
                tx.id,
                organization_id=request.organization_id,
                status=MpesaTransactionStatus.FAILED.value,
                result_code=int(response_code) if response_code.isdigit() else None,
                result_desc=str(error),
                metadata={"daraja_response": raw},
            )
            await db_client.append_event(
                transaction_id=tx.id,
                event_type=MpesaEventType.STK_INIT_FAILED.value,
                payload=raw,
            )
            return STKPushResponse(
                success=False,
                transaction_id=tx.id,
                error=str(error),
                raw_response=raw,
            )

        checkout_request_id = raw.get("CheckoutRequestID")
        merchant_request_id = raw.get("MerchantRequestID")
        await db_client.update_transaction(
            tx.id,
            organization_id=request.organization_id,
            status=MpesaTransactionStatus.INITIATED.value,
            checkout_request_id=checkout_request_id,
            merchant_request_id=merchant_request_id,
            metadata={"daraja_response": raw},
        )
        await db_client.append_event(
            transaction_id=tx.id,
            event_type=MpesaEventType.STK_INITIATED.value,
            payload=raw,
        )
        try:
            from api.services.durable_execution.bridge import get_durable_execution_bridge
            from api.services.platform_events.adapters import publish_payment_initiated

            bridge = get_durable_execution_bridge()
            await bridge.start_mpesa_payment_wait(
                organization_id=request.organization_id,
                transaction_id=tx.id,
                workflow_run_id=request.workflow_run_id,
            )
            await publish_payment_initiated(
                organization_id=request.organization_id,
                transaction_id=tx.id,
                workflow_run_id=request.workflow_run_id,
                phone_e164=phone,
                amount=request.amount,
            )
        except Exception as exc:
            logger.debug("durable/mpesa platform event start skipped: {}", exc)

        await self._schedule_verification(tx.id, request.organization_id)

        return STKPushResponse(
            success=True,
            transaction_id=tx.id,
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            customer_message=raw.get("CustomerMessage"),
            raw_response=raw,
        )

    async def get_transaction(
        self,
        transaction_id: int,
        *,
        organization_id: int,
    ) -> dict[str, Any] | None:
        tx = await db_client.get_transaction(transaction_id, organization_id=organization_id)
        if not tx:
            return None
        events = await db_client.list_events(
            transaction_id=transaction_id,
            organization_id=organization_id,
        )
        return {
            "id": tx.id,
            "organization_id": tx.organization_id,
            "workflow_run_id": tx.workflow_run_id,
            "phone_e164": tx.phone_e164,
            "amount": tx.amount,
            "currency": tx.currency,
            "account_reference": tx.account_reference,
            "transaction_desc": tx.transaction_desc,
            "merchant_request_id": tx.merchant_request_id,
            "checkout_request_id": tx.checkout_request_id,
            "mpesa_receipt_number": tx.mpesa_receipt_number,
            "status": tx.status,
            "result_code": tx.result_code,
            "result_desc": tx.result_desc,
            "metadata": tx.metadata_json or {},
            "created_at": tx.created_at,
            "updated_at": tx.updated_at,
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "payload": e.payload,
                    "created_at": e.created_at,
                }
                for e in events
            ],
        }

    async def _schedule_verification(self, transaction_id: int, organization_id: int) -> None:
        from api.tasks.arq import get_arq_redis

        delay = (
            MPESA_STK_QUERY_DELAY_S_PROD
            if KENYA_PRODUCTION_MODE
            else MPESA_STK_QUERY_DELAY_S
        )
        redis = await get_arq_redis()
        await redis.enqueue_job(
            FunctionNames.VERIFY_MPESA_TRANSACTION,
            transaction_id,
            organization_id,
            _defer_by=int(delay),
        )

    async def process_callback(
        self,
        *,
        organization_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._callbacks.process_stk_callback(
            organization_id=organization_id,
            payload=payload,
        )

    async def verify_transaction(
        self,
        transaction_id: int,
        *,
        organization_id: int,
    ) -> dict[str, Any]:
        config = await self.load_org_config(organization_id)
        return await self._verification.verify_transaction(
            transaction_id,
            organization_id=organization_id,
            config=config,
        )


class MpesaAsyncPipeline:
    """Async processing pipeline for M-Pesa events."""

    def __init__(self) -> None:
        self._stk = STKPushService()
        self._callbacks = MpesaCallbackProcessor()

    async def enqueue_callback(self, organization_id: int, payload: dict[str, Any]) -> None:
        from api.tasks.arq import enqueue_job

        await enqueue_job(
            FunctionNames.PROCESS_MPESA_CALLBACK,
            organization_id,
            payload,
        )

    async def process_callback(self, organization_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._callbacks.process_stk_callback(
            organization_id=organization_id,
            payload=payload,
        )

    async def verify_pending_transactions(self) -> int:
        from api.tasks.arq import enqueue_job

        cutoff = datetime.now(UTC) - timedelta(seconds=MPESA_STK_QUERY_DELAY_S)
        pending = await db_client.list_pending_for_verification(older_than=cutoff)
        processed = 0
        for tx in pending:
            try:
                await enqueue_job(
                    FunctionNames.VERIFY_MPESA_TRANSACTION,
                    tx.id,
                    tx.organization_id,
                )
                processed += 1
            except Exception:
                logger.exception("Failed to enqueue M-Pesa verification for tx {}", tx.id)
        return processed

    async def retry_failed_initiation(
        self,
        transaction_id: int,
        *,
        organization_id: int,
    ) -> STKPushResponse:
        tx = await db_client.get_transaction(transaction_id, organization_id=organization_id)
        if not tx:
            return STKPushResponse(success=False, error="transaction_not_found")
        if tx.status != MpesaTransactionStatus.FAILED.value:
            return STKPushResponse(success=False, error="transaction_not_retryable")

        request = STKPushRequest(
            phone_e164=tx.phone_e164,
            amount=tx.amount,
            account_reference=tx.account_reference,
            transaction_desc=tx.transaction_desc,
            organization_id=organization_id,
            workflow_run_id=tx.workflow_run_id,
            metadata={"retry_of": transaction_id},
        )
        await db_client.append_event(
            transaction_id=transaction_id,
            event_type=MpesaEventType.RETRY_SCHEDULED.value,
            payload={"retry": True},
        )
        return await self._stk.initiate_stk_push(request)
