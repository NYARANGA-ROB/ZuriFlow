from __future__ import annotations

from typing import Any

from api.services.whatsapp.messaging import WhatsAppMessagingService
from api.services.whatsapp.post_call.types import PostCallStep, PostCallSummary, StepResult
from api.services.whatsapp.templates.engine import WhatsAppTemplateEngine
from api.services.whatsapp.templates.i18n import LOCALIZED_TEMPLATES
from api.services.whatsapp.types import WhatsAppTemplateName


class WhatsAppDispatcher:
    """Send post-call WhatsApp messages with localized templates and persistence."""

    def __init__(
        self,
        *,
        messaging: WhatsAppMessagingService | None = None,
    ) -> None:
        self._messaging = messaging or WhatsAppMessagingService()

    async def send_summary(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        customer_name: str,
        summary: PostCallSummary,
        workflow_run_id: int,
        provider: str | None = None,
    ) -> StepResult:
        templates = WhatsAppTemplateEngine(LOCALIZED_TEMPLATES.get(summary.language, {}))
        body = templates.render(
            WhatsAppTemplateName.CALL_SUMMARY.value,
            {
                "customer_name": customer_name,
                "summary": summary.text,
                "intent": summary.intent,
                "next_steps": summary.next_steps,
            },
        )
        result = await self._messaging.send_text(
            organization_id=organization_id,
            phone_e164=phone_e164,
            body=body,
            provider=provider,
            template_name=WhatsAppTemplateName.CALL_SUMMARY.value,
            workflow_run_id=workflow_run_id,
            metadata={"language": summary.language, "step": PostCallStep.SEND_SUMMARY.value},
        )
        return StepResult(
            step=PostCallStep.SEND_SUMMARY,
            success=bool(result.get("success")),
            detail=result,
            error=result.get("error"),
        )

    async def send_payment_link(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        customer_name: str,
        summary: PostCallSummary,
        payment_url: str,
        workflow_run_id: int,
        provider: str | None = None,
    ) -> StepResult:
        amount = summary.slots.get("amount") or summary.slots.get("payment_amount") or ""
        reference = summary.slots.get("reference") or summary.slots.get("account_ref") or ""
        templates = WhatsAppTemplateEngine(LOCALIZED_TEMPLATES.get(summary.language, {}))
        body = templates.render(
            WhatsAppTemplateName.PAYMENT_LINK.value,
            {
                "customer_name": customer_name,
                "amount": amount or "your payment",
                "payment_url": payment_url,
                "reference": reference,
            },
        )
        result = await self._messaging.send_text(
            organization_id=organization_id,
            phone_e164=phone_e164,
            body=body,
            provider=provider,
            template_name=WhatsAppTemplateName.PAYMENT_LINK.value,
            workflow_run_id=workflow_run_id,
            metadata={"language": summary.language, "step": PostCallStep.SEND_PAYMENT_LINK.value},
        )
        return StepResult(
            step=PostCallStep.SEND_PAYMENT_LINK,
            success=bool(result.get("success")),
            detail=result,
            error=result.get("error"),
        )

    async def send_booking_link(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        customer_name: str,
        summary: PostCallSummary,
        booking_url: str,
        workflow_run_id: int,
        provider: str | None = None,
        appointment_date: str = "",
        appointment_time: str = "",
        location: str = "",
    ) -> StepResult:
        templates = WhatsAppTemplateEngine(LOCALIZED_TEMPLATES.get(summary.language, {}))
        body = templates.render(
            WhatsAppTemplateName.APPOINTMENT_CONFIRMATION.value,
            {
                "customer_name": customer_name,
                "appointment_date": appointment_date or summary.slots.get("appointment_date", "TBC"),
                "appointment_time": appointment_time or summary.slots.get("appointment_time", "TBC"),
                "location": location or summary.slots.get("location", ""),
                "booking_url": booking_url,
            },
        )
        if booking_url and booking_url not in body:
            body = f"{body}\n\n{booking_url}"

        result = await self._messaging.send_text(
            organization_id=organization_id,
            phone_e164=phone_e164,
            body=body,
            provider=provider,
            template_name=WhatsAppTemplateName.APPOINTMENT_CONFIRMATION.value,
            workflow_run_id=workflow_run_id,
            metadata={"language": summary.language, "step": PostCallStep.SEND_BOOKING_LINK.value},
        )
        return StepResult(
            step=PostCallStep.SEND_BOOKING_LINK,
            success=bool(result.get("success")),
            detail=result,
            error=result.get("error"),
        )
