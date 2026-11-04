from __future__ import annotations

from loguru import logger

from api.db import db_client
from api.services.mpesa_daraja.pipeline import STKPushService
from api.services.mpesa_daraja.types import MpesaEventType, MpesaTransactionStatus, STKPushRequest
from api.services.voice_mpesa.config import VoiceMpesaConfig
from api.services.voice_mpesa.types import VoicePaymentSession, VoicePaymentState


class VoicePaymentRecovery:
    """Retry STK push and resume interrupted payment flows."""

    def __init__(self, *, stk: STKPushService | None = None) -> None:
        self._stk = stk or STKPushService()

    async def retry_stk_push(
        self,
        session: VoicePaymentSession,
        config: VoiceMpesaConfig,
    ) -> tuple[bool, str | None, int | None]:
        if session.retry_count >= config.max_retries:
            return False, "max_retries_exceeded", session.transaction_id

        session.retry_count += 1
        if session.transaction_id:
            await self._log_voice_event(
                session.transaction_id,
                MpesaEventType.RETRY_SCHEDULED.value,
                {"retry_count": session.retry_count, "source": "voice_workflow"},
            )

        response = await self._stk.initiate_stk_push(
            STKPushRequest(
                phone_e164=session.phone_e164,
                amount=session.amount,
                account_reference=session.account_reference or f"RUN{session.workflow_run_id}",
                transaction_desc="VoicePay",
                organization_id=session.organization_id,
                workflow_run_id=session.workflow_run_id,
                metadata={
                    "voice_session_id": session.session_id,
                    "voice_retry": session.retry_count,
                },
            )
        )
        if not response.success:
            return False, response.error, response.transaction_id

        session.transaction_id = response.transaction_id
        return True, None, response.transaction_id

    async def resume_after_interrupt(self, session: VoicePaymentSession) -> VoicePaymentState:
        session.interrupted = False
        if session.interrupted_from:
            restored = session.interrupted_from
            session.interrupted_from = None
            return restored
        if session.transaction_id:
            tx = await db_client.get_transaction(
                session.transaction_id,
                organization_id=session.organization_id,
            )
            if tx and tx.status == MpesaTransactionStatus.COMPLETED.value:
                return VoicePaymentState.PAYMENT_CONFIRMED
            if tx and tx.status in {
                MpesaTransactionStatus.INITIATED.value,
                MpesaTransactionStatus.PENDING.value,
            }:
                return VoicePaymentState.AWAITING_PAYMENT
        return VoicePaymentState.AWAITING_CONSENT

    @staticmethod
    async def _log_voice_event(
        transaction_id: int,
        event_type: str,
        payload: dict,
    ) -> None:
        try:
            await db_client.append_event(
                transaction_id=transaction_id,
                event_type=event_type,
                payload=payload,
            )
        except Exception:
            logger.exception("Failed to log voice M-Pesa event tx={}", transaction_id)
