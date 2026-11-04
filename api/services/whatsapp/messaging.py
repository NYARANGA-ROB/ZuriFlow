from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client
from api.services.whatsapp.config import ORG_CONFIG_KEY, WhatsAppOrgConfig
from api.services.org_config_cache import whatsapp_config_cache
from api.services.whatsapp.conversation import WhatsAppConversationStore
from api.services.whatsapp.providers.factory import get_whatsapp_provider
from api.services.whatsapp.queue import WhatsAppRetryQueue
from api.services.whatsapp.templates.engine import WhatsAppTemplateEngine
from api.services.whatsapp.types import (
    MessageStatus,
    OutboundPayload,
    WhatsAppProviderName,
    WhatsAppTemplateName,
)
from api.utils.telephony_address import normalize_telephony_address


class WhatsAppMessagingService:
    """High-level WhatsApp messaging for voice-agent follow-ups."""

    def __init__(
        self,
        *,
        store: WhatsAppConversationStore | None = None,
        templates: WhatsAppTemplateEngine | None = None,
        queue: WhatsAppRetryQueue | None = None,
    ) -> None:
        self._store = store or WhatsAppConversationStore()
        self._templates = templates or WhatsAppTemplateEngine()
        self._queue = queue or WhatsAppRetryQueue()

    async def load_org_config(self, organization_id: int) -> WhatsAppOrgConfig:
        cache = whatsapp_config_cache()
        cached = cache.get(organization_id, ORG_CONFIG_KEY)
        if cached is not None:
            return cached
        row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
        config = WhatsAppOrgConfig.from_dict(row.value if row else None)
        cache.set(organization_id, ORG_CONFIG_KEY, config)
        return config

    def _resolve_provider(
        self,
        config: WhatsAppOrgConfig,
        provider: str | None = None,
    ) -> str:
        return (provider or config.default_provider).lower()

    async def send_text(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        body: str,
        provider: str | None = None,
        template_name: str | None = None,
        workflow_run_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        queue_on_failure: bool = True,
    ) -> dict[str, Any]:
        config = await self.load_org_config(organization_id)
        if not config.enabled:
            return {"success": False, "error": "WhatsApp is disabled for this organization"}

        provider_name = self._resolve_provider(config, provider)
        phone = normalize_telephony_address(phone_e164)

        conversation = await self._store.get_or_create(
            organization_id=organization_id,
            phone_e164=phone,
            provider=provider_name,
            workflow_run_id=workflow_run_id,
            metadata=metadata,
        )
        message = await self._store.record_outbound(
            conversation_id=conversation.id,
            body=body,
            template_name=template_name,
            status=MessageStatus.PENDING,
            metadata=metadata,
        )

        result = await self._dispatch_send(
            organization_id=organization_id,
            config=config,
            provider_name=provider_name,
            phone=phone,
            body=body,
            conversation_id=conversation.id,
            message_id=message.id,
            workflow_run_id=workflow_run_id,
            template_name=template_name,
            metadata=metadata,
        )

        if not result["success"] and queue_on_failure:
            await self._queue.enqueue_retry(
                OutboundPayload(
                    organization_id=organization_id,
                    phone_e164=phone,
                    body=body,
                    provider=WhatsAppProviderName(provider_name),
                    template_name=template_name,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    workflow_run_id=workflow_run_id,
                    metadata=metadata or {},
                )
            )

        if organization_id > 0:
            from api.services.voice_analytics.integration import track_whatsapp_delivery

            track_whatsapp_delivery(
                organization_id=organization_id,
                success=bool(result.get("success")),
                workflow_run_id=workflow_run_id or 0,
                message_id=message.id,
                template_name=template_name or "",
            )
            try:
                from api.services.platform_events.adapters import publish_whatsapp_message

                await publish_whatsapp_message(
                    organization_id=organization_id,
                    phone_e164=phone,
                    success=bool(result.get("success")),
                    conversation_id=conversation.id,
                    message_id=message.id,
                    workflow_run_id=workflow_run_id,
                    template_name=template_name,
                    body=body[:500] if body else None,
                    error=result.get("error"),
                )
            except Exception as exc:
                logger.debug("platform whatsapp event publish skipped: {}", exc)

        return {
            **result,
            "conversation_id": conversation.id,
            "message_id": message.id,
        }

    async def send_rendered_template(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        template_name: str,
        variables: dict[str, Any],
        provider: str | None = None,
        workflow_run_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = self._templates.render(template_name, variables)
        return await self.send_text(
            organization_id=organization_id,
            phone_e164=phone_e164,
            body=body,
            provider=provider,
            template_name=template_name,
            workflow_run_id=workflow_run_id,
            metadata=metadata,
        )

    async def send_call_summary(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        customer_name: str,
        summary: str,
        intent: str = "",
        next_steps: str = "",
        workflow_run_id: int | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        return await self.send_rendered_template(
            organization_id=organization_id,
            phone_e164=phone_e164,
            template_name=WhatsAppTemplateName.CALL_SUMMARY.value,
            variables={
                "customer_name": customer_name,
                "summary": summary,
                "intent": intent,
                "next_steps": next_steps,
            },
            provider=provider,
            workflow_run_id=workflow_run_id,
        )

    async def send_payment_link(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        customer_name: str,
        amount: str,
        payment_url: str,
        reference: str = "",
        workflow_run_id: int | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        return await self.send_rendered_template(
            organization_id=organization_id,
            phone_e164=phone_e164,
            template_name=WhatsAppTemplateName.PAYMENT_LINK.value,
            variables={
                "customer_name": customer_name,
                "amount": amount,
                "payment_url": payment_url,
                "reference": reference,
            },
            provider=provider,
            workflow_run_id=workflow_run_id,
        )

    async def send_appointment_confirmation(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        customer_name: str,
        appointment_date: str,
        appointment_time: str,
        location: str = "",
        workflow_run_id: int | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        return await self.send_rendered_template(
            organization_id=organization_id,
            phone_e164=phone_e164,
            template_name=WhatsAppTemplateName.APPOINTMENT_CONFIRMATION.value,
            variables={
                "customer_name": customer_name,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "location": location,
            },
            provider=provider,
            workflow_run_id=workflow_run_id,
        )

    async def handle_inbound(
        self,
        *,
        organization_id: int,
        provider_name: str,
        inbound,
    ) -> dict[str, Any]:
        config = await self.load_org_config(organization_id)
        phone = normalize_telephony_address(inbound.from_phone)
        conversation = await self._store.get_or_create(
            organization_id=organization_id,
            phone_e164=phone,
            provider=provider_name,
            metadata={"profile_name": inbound.profile_name},
        )
        message = await self._store.record_inbound(
            conversation_id=conversation.id,
            body=inbound.body,
            provider_message_id=inbound.provider_message_id,
            metadata={"raw": inbound.raw_payload},
        )

        escalated = False
        if self._should_escalate(inbound.body):
            from api.services.whatsapp.escalation import WhatsAppEscalationService

            escalation = WhatsAppEscalationService(store=self._store, templates=self._templates)
            await escalation.escalate(
                self,
                organization_id=organization_id,
                conversation_id=conversation.id,
                reason="Customer requested human agent via WhatsApp",
                context=inbound.body,
                customer_phone=phone,
            )
            escalated = True

        return {
            "conversation_id": conversation.id,
            "message_id": message.id,
            "escalated": escalated,
        }

    async def process_outbound_payload(self, payload_dict: dict[str, Any]) -> dict[str, Any]:
        provider_enum = payload_dict["provider"]
        if isinstance(provider_enum, str):
            provider_enum = WhatsAppProviderName(provider_enum)

        payload = OutboundPayload(
            organization_id=payload_dict["organization_id"],
            phone_e164=payload_dict["phone_e164"],
            body=payload_dict["body"],
            provider=provider_enum,
            template_name=payload_dict.get("template_name"),
            conversation_id=payload_dict.get("conversation_id"),
            message_id=payload_dict.get("message_id"),
            workflow_run_id=payload_dict.get("workflow_run_id"),
            metadata=payload_dict.get("metadata") or {},
            attempt=payload_dict.get("attempt", 1),
        )

        config = await self.load_org_config(payload.organization_id)
        provider_name = payload.provider.value
        result = await self._dispatch_send(
            organization_id=payload.organization_id,
            config=config,
            provider_name=provider_name,
            phone=payload.phone_e164,
            body=payload.body,
            conversation_id=payload.conversation_id,
            message_id=payload.message_id,
            workflow_run_id=payload.workflow_run_id,
            template_name=payload.template_name,
            metadata=payload.metadata,
        )

        if not result["success"]:
            retried = await self._queue.enqueue_retry(payload)
            result["queued_retry"] = retried
        return result

    async def _dispatch_send(
        self,
        *,
        organization_id: int,
        config: WhatsAppOrgConfig,
        provider_name: str,
        phone: str,
        body: str,
        conversation_id: int | None,
        message_id: int | None,
        workflow_run_id: int | None,
        template_name: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            provider = get_whatsapp_provider(provider_name, config)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        send_result = await provider.send_text(
            phone,
            body,
            rendered_body=body,
            status_callback=metadata.get("status_callback") if metadata else None,
        )

        if message_id is not None:
            status = MessageStatus.SENT if send_result.success else MessageStatus.FAILED
            await self._store.update_message_status(
                message_id=message_id,
                status=status,
                provider_message_id=send_result.provider_message_id,
                metadata={"error": send_result.error, "raw": send_result.raw_response},
            )

        if not send_result.success:
            logger.warning(
                "WhatsApp send failed org={} phone={} error={}",
                organization_id,
                phone,
                send_result.error,
            )

        return {
            "success": send_result.success,
            "provider_message_id": send_result.provider_message_id,
            "error": send_result.error,
            "workflow_run_id": workflow_run_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "template_name": template_name,
        }

    @staticmethod
    def _should_escalate(body: str) -> bool:
        lowered = body.lower().strip()
        triggers = (
            "human",
            "agent",
            "representative",
            "speak to someone",
            "talk to someone",
            "customer care",
        )
        return any(trigger in lowered for trigger in triggers)
