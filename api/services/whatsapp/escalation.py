from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from api.services.whatsapp.config import WhatsAppOrgConfig
from api.services.whatsapp.conversation import WhatsAppConversationStore
from api.services.whatsapp.messaging import WhatsAppMessagingService
from api.services.whatsapp.templates.engine import WhatsAppTemplateEngine
from api.services.whatsapp.types import WhatsAppTemplateName


class WhatsAppEscalationService:
    """Route conversations to human agents via WhatsApp and optional webhooks."""

    def __init__(
        self,
        *,
        store: WhatsAppConversationStore | None = None,
        templates: WhatsAppTemplateEngine | None = None,
    ) -> None:
        self._store = store or WhatsAppConversationStore()
        self._templates = templates or WhatsAppTemplateEngine()

    async def escalate(
        self,
        messaging: WhatsAppMessagingService,
        *,
        organization_id: int,
        conversation_id: int,
        reason: str,
        context: str = "",
        customer_phone: str | None = None,
    ) -> dict[str, Any]:
        conversation = await self._store.mark_escalated(
            conversation_id=conversation_id,
            organization_id=organization_id,
            reason=reason,
        )
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        config = await messaging.load_org_config(organization_id)
        phone = customer_phone or conversation.phone_e164
        notify_results: list[dict[str, Any]] = []

        handoff_body = self._templates.render(
            WhatsAppTemplateName.ESCALATION_HANDOFF.value,
            {
                "customer_phone": phone,
                "reason": reason,
                "context": context,
            },
        )

        try:
            customer_ack_body = self._templates.render("escalation_customer_ack", {})
        except KeyError:
            customer_ack_body = (
                "Thanks for your patience. A human agent will follow up with you "
                "on WhatsApp shortly."
            )

        for notify_phone in config.escalation.notify_numbers:
            result = await messaging.send_text(
                organization_id=organization_id,
                phone_e164=notify_phone,
                body=handoff_body,
                template_name=WhatsAppTemplateName.ESCALATION_HANDOFF.value,
                workflow_run_id=conversation.workflow_run_id,
                metadata={"escalation_for_conversation_id": conversation_id},
            )
            notify_results.append(
                {
                    "phone": notify_phone,
                    "success": result.get("success", False),
                    "message_id": result.get("message_id"),
                }
            )

        if config.escalation.webhook_url:
            await self._notify_webhook(
                config.escalation.webhook_url,
                {
                    "organization_id": organization_id,
                    "conversation_id": conversation_id,
                    "customer_phone": phone,
                    "reason": reason,
                    "context": context,
                },
            )

        customer_ack = await messaging.send_text(
            organization_id=organization_id,
            phone_e164=phone,
            body=customer_ack_body,
            workflow_run_id=conversation.workflow_run_id,
            metadata={"escalation_ack": True},
        )

        return {
            "conversation_id": conversation_id,
            "escalated": True,
            "notify_results": notify_results,
            "customer_ack": customer_ack,
        }

    async def _notify_webhook(self, url: str, payload: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code >= 400:
                    logger.warning(
                        "WhatsApp escalation webhook failed: {} {}",
                        response.status_code,
                        response.text,
                    )
        except Exception:
            logger.exception("WhatsApp escalation webhook error")
