"""ARQ tasks for M-Pesa Daraja async processing."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.services.mpesa_daraja.pipeline import MpesaAsyncPipeline, STKPushService

_pipeline = MpesaAsyncPipeline()
_stk = STKPushService()


async def process_mpesa_callback(
    _ctx: dict[str, Any],
    organization_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        return await _pipeline.process_callback(organization_id, payload)
    except Exception:
        logger.exception(
            "M-Pesa callback processing failed org={} checkout={}",
            organization_id,
            (payload.get("Body") or {}).get("stkCallback", {}).get("CheckoutRequestID"),
        )
        raise


async def verify_mpesa_transaction(
    _ctx: dict[str, Any],
    transaction_id: int,
    organization_id: int,
) -> dict[str, Any]:
    return await _stk.verify_transaction(transaction_id, organization_id=organization_id)


async def verify_all_pending_mpesa_transactions(_ctx: dict[str, Any]) -> dict[str, Any]:
    """Sweep pending STK transactions and enqueue verification jobs."""
    count = await _pipeline.verify_pending_transactions()
    logger.info("M-Pesa pending verification sweep enqueued {} jobs", count)
    return {"enqueued": count}
