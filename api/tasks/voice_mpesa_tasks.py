"""ARQ tasks for voice-driven M-Pesa payment workflow."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client
from api.services.mpesa_daraja.types import MpesaTransactionStatus
from api.services.voice_mpesa.engine import get_voice_mpesa_engine
from api.services.voice_mpesa.receipt import VoiceMpesaReceiptSender


async def voice_mpesa_send_receipt(
    _ctx: dict[str, Any],
    session_id: str,
    organization_id: int,
) -> dict[str, Any]:
    engine = get_voice_mpesa_engine()
    session = engine.get_session(session_id)
    if not session:
        return {"success": False, "error": "session_not_found"}

    sender = VoiceMpesaReceiptSender()
    result = await sender.send_text_receipt(session)
    if result.get("success"):
        await engine.mark_receipt_sent(session_id)
        if session.transaction_id:
            await db_client.append_event(
                transaction_id=session.transaction_id,
                event_type="voice_receipt_sent",
                payload=result,
            )
    return result


async def voice_mpesa_complete_payment(
    _ctx: dict[str, Any],
    transaction_id: int,
    organization_id: int,
) -> dict[str, Any]:
    engine = get_voice_mpesa_engine()
    tx = await db_client.get_transaction(transaction_id, organization_id=organization_id)
    if not tx:
        return {"success": False, "error": "transaction_not_found"}

    await engine.on_payment_callback(
        transaction_id=transaction_id,
        organization_id=organization_id,
        status=tx.status,
        mpesa_receipt_number=tx.mpesa_receipt_number,
    )
    session = engine._find_session_by_transaction(transaction_id, organization_id)
    if session and tx.status == MpesaTransactionStatus.COMPLETED.value:
        logger.info(
            "Voice M-Pesa payment completed session={} receipt={}",
            session.session_id,
            tx.mpesa_receipt_number,
        )
        from api.services.voice_analytics.integration import track_payment_success

        track_payment_success(
            organization_id=organization_id,
            session_id=session.session_id,
            workflow_run_id=session.workflow_run_id,
            amount=float(session.amount) if session.amount else None,
            receipt=tx.mpesa_receipt_number or "",
            language=session.language,
        )
    return {"success": True, "status": tx.status}
