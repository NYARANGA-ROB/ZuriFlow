from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client
from api.services.mpesa_daraja.client import DarajaClient
from api.services.mpesa_daraja.config import MpesaDarajaConfig
from api.services.mpesa_daraja.types import (
    MpesaEventType,
    MpesaTransactionStatus,
    STKQueryResult,
)


class TransactionVerificationService:
    """Verify pending STK transactions via Daraja STK Push Query."""

    async def verify_transaction(
        self,
        transaction_id: int,
        *,
        organization_id: int,
        config: MpesaDarajaConfig,
    ) -> dict[str, Any]:
        tx = await db_client.get_transaction(transaction_id, organization_id=organization_id)
        if not tx:
            return {"success": False, "error": "transaction_not_found"}
        if tx.status in (
            MpesaTransactionStatus.COMPLETED.value,
            MpesaTransactionStatus.FAILED.value,
            MpesaTransactionStatus.CANCELLED.value,
        ):
            return {"success": True, "status": tx.status, "already_final": True}
        if not tx.checkout_request_id:
            return {"success": False, "error": "missing_checkout_request_id"}

        client = DarajaClient(config)
        query = await client.stk_push_query(tx.checkout_request_id)
        await db_client.append_event(
            transaction_id=tx.id,
            event_type=MpesaEventType.QUERY_RESULT.value,
            payload=query.raw_response,
        )

        return await self._apply_query_result(tx.id, organization_id, query)

    async def _apply_query_result(
        self,
        transaction_id: int,
        organization_id: int,
        query: STKQueryResult,
    ) -> dict[str, Any]:
        if query.result_code == 0:
            await db_client.update_transaction(
                transaction_id,
                organization_id=organization_id,
                status=MpesaTransactionStatus.COMPLETED.value,
                result_code=query.result_code,
                result_desc=query.result_desc,
            )
            await db_client.append_event(
                transaction_id=transaction_id,
                event_type=MpesaEventType.VERIFIED.value,
                payload={"source": "stk_query", **query.raw_response},
            )
            return {"success": True, "status": MpesaTransactionStatus.COMPLETED.value}

        # 1032 = cancelled by user, 1 = insufficient funds, etc.
        terminal_codes = {1032, 1, 2001}
        if query.result_code in terminal_codes:
            status = (
                MpesaTransactionStatus.CANCELLED.value
                if query.result_code == 1032
                else MpesaTransactionStatus.FAILED.value
            )
            await db_client.update_transaction(
                transaction_id,
                organization_id=organization_id,
                status=status,
                result_code=query.result_code,
                result_desc=query.result_desc,
            )
            return {"success": True, "status": status}

        if query.result_desc and "timeout" in query.result_desc.lower():
            await db_client.update_transaction(
                transaction_id,
                organization_id=organization_id,
                status=MpesaTransactionStatus.TIMEOUT.value,
                result_code=query.result_code,
                result_desc=query.result_desc,
            )
            return {"success": True, "status": MpesaTransactionStatus.TIMEOUT.value}

        logger.info(
            "STK query still pending tx={} code={} desc={}",
            transaction_id,
            query.result_code,
            query.result_desc,
        )
        return {
            "success": False,
            "pending": True,
            "result_code": query.result_code,
            "result_desc": query.result_desc,
        }
