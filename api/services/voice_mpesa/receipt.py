from __future__ import annotations

from loguru import logger

from api.services.voice_mpesa.confirmation import VoicePaymentConfirmation
from api.services.voice_mpesa.types import VoicePaymentSession
from api.services.whatsapp.messaging import WhatsAppMessagingService
from api.services.whatsapp.types import WhatsAppTemplateName


class VoiceMpesaReceiptSender:
    """Send WhatsApp payment receipts after voice-confirmed M-Pesa payments."""

    def __init__(
        self,
        *,
        messaging: WhatsAppMessagingService | None = None,
        confirmation: VoicePaymentConfirmation | None = None,
    ) -> None:
        self._messaging = messaging or WhatsAppMessagingService()
        self._confirmation = confirmation or VoicePaymentConfirmation()

    async def send_receipt(
        self,
        session: VoicePaymentSession,
        *,
        payment_url: str | None = None,
    ) -> dict:
        reference = session.mpesa_receipt_number or session.account_reference
        body_hint = self._confirmation.success_prompt(
            amount=session.amount,
            currency="KES",
            receipt=reference,
            language=session.language,
        )

        if payment_url:
            return await self._messaging.send_payment_link(
                organization_id=session.organization_id,
                phone_e164=session.phone_e164,
                customer_name=session.customer_name,
                amount=f"KES {session.amount:g}",
                payment_url=payment_url,
                reference=reference or "",
                workflow_run_id=session.workflow_run_id,
            )

        return await self._messaging.send_rendered_template(
            organization_id=session.organization_id,
            phone_e164=session.phone_e164,
            template_name=WhatsAppTemplateName.PAYMENT_LINK.value,
            variables={
                "customer_name": session.customer_name,
                "amount": f"KES {session.amount:g}",
                "payment_url": f"Receipt: {reference}",
                "reference": reference or "",
            },
            workflow_run_id=session.workflow_run_id,
            metadata={
                "voice_mpesa_receipt": True,
                "transaction_id": session.transaction_id,
                "receipt_body": body_hint,
            },
        )

    async def send_text_receipt(self, session: VoicePaymentSession) -> dict:
        body = self._confirmation.success_prompt(
            amount=session.amount,
            currency="KES",
            receipt=session.mpesa_receipt_number,
            language=session.language,
        )
        body += "\n\nAsante for your payment."
        try:
            return await self._messaging.send_text(
                organization_id=session.organization_id,
                phone_e164=session.phone_e164,
                body=body,
                workflow_run_id=session.workflow_run_id,
                metadata={
                    "voice_mpesa_receipt": True,
                    "transaction_id": session.transaction_id,
                    "mpesa_receipt_number": session.mpesa_receipt_number,
                },
            )
        except Exception:
            logger.exception(
                "WhatsApp receipt failed session={} tx={}",
                session.session_id,
                session.transaction_id,
            )
            return {"success": False}
