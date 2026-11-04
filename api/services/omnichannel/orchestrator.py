"""Channel orchestration nodes for unified customer journeys."""

from __future__ import annotations

from typing import Any

from api.services.omnichannel.adapters import adapter_for
from api.services.omnichannel.consent import get_consent_service
from api.services.omnichannel.conversations import get_conversation_service
from api.services.omnichannel.types import (
    Channel,
    MessagePurpose,
    OrchestrationAction,
)

_ACTION_CHANNEL: dict[OrchestrationAction, Channel | None] = {
    OrchestrationAction.SEND_SMS: Channel.SMS,
    OrchestrationAction.SEND_WHATSAPP: Channel.WHATSAPP,
    OrchestrationAction.START_CALL: Channel.VOICE,
    OrchestrationAction.WAIT_FOR_REPLY: None,
    OrchestrationAction.SEND_RECEIPT: None,
    OrchestrationAction.SEND_DOCUMENT: None,
    OrchestrationAction.ESCALATE: Channel.VOICE,
}

_RECEIPT_FALLBACK = (Channel.SMS, Channel.WHATSAPP, Channel.WEB_CHAT)


class ChannelOrchestrator:
    async def execute(
        self,
        *,
        organization_id: int,
        action: OrchestrationAction | str,
        phone: str | None = None,
        email: str | None = None,
        whatsapp_id: str | None = None,
        crm_id: str | None = None,
        customer_id: int | None = None,
        body: str | None = None,
        purpose: MessagePurpose | str = MessagePurpose.TRANSACTIONAL,
        channel: Channel | str | None = None,
        workflow_run_id: int | None = None,
        transaction_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action = OrchestrationAction(action)
        purpose = MessagePurpose(purpose)
        conversations = get_conversation_service()
        consent = get_consent_service()

        origin = Channel(channel) if channel else _ACTION_CHANNEL.get(action) or Channel.SMS
        identity, conversation = await conversations.get_or_open(
            organization_id=organization_id,
            channel=origin,
            phone=phone,
            email=email,
            whatsapp_id=whatsapp_id,
            crm_id=crm_id,
            customer_id=customer_id,
        )

        if action == OrchestrationAction.WAIT_FOR_REPLY:
            from api.db import db_client

            await db_client.update_conversation(
                conversation.id,
                organization_id=organization_id,
                waiting_for_reply=True,
                status="open",
            )
            await conversations.append(
                organization_id=organization_id,
                conversation_id=conversation.id,
                customer_id=identity.customer_id,
                channel=origin,
                direction="system",
                message_type="wait",
                body=body or "Waiting for customer reply",
                status="waiting",
                metadata=metadata,
            )
            return {
                "action": action.value,
                "status": "waiting",
                "conversation_id": conversation.id,
                "customer_id": identity.customer_id,
            }

        target = self._target_channel(action, origin)
        decision = await consent.decide(
            organization_id=organization_id,
            customer_id=identity.customer_id,
            channel=target,
            purpose=purpose,
        )
        if not decision.allowed:
            await conversations.append(
                organization_id=organization_id,
                conversation_id=conversation.id,
                customer_id=identity.customer_id,
                channel=target,
                direction="outbound",
                message_type="blocked",
                body=body,
                status="blocked",
                consent_allowed=False,
                metadata={"reason": decision.reason, **(metadata or {})},
            )
            return {
                "action": action.value,
                "status": "blocked",
                "consent": decision.to_dict(),
                "conversation_id": conversation.id,
                "customer_id": identity.customer_id,
            }

        text = body or self._default_body(action)
        send = await adapter_for(target).send(
            organization_id=organization_id,
            to=phone or whatsapp_id or email or str(identity.customer_id),
            body=text,
            message_type=self._message_type(action),
            metadata={
                **(metadata or {}),
                "action": action.value,
                "workflow_run_id": workflow_run_id,
            },
        )
        message = await conversations.append(
            organization_id=organization_id,
            conversation_id=conversation.id,
            customer_id=identity.customer_id,
            channel=target,
            direction="outbound",
            message_type=self._message_type(action),
            body=text,
            status=send.status if send.success else "failed",
            provider_message_id=send.provider_message_id,
            workflow_run_id=workflow_run_id,
            transaction_id=transaction_id,
            consent_allowed=True,
            metadata={"action": action.value, **send.metadata},
        )
        return {
            "action": action.value,
            "status": send.status if send.success else "failed",
            "success": send.success,
            "channel": target.value,
            "conversation_id": conversation.id,
            "customer_id": identity.customer_id,
            "message_id": message.id,
            "consent": decision.to_dict(),
            "send": send.to_dict(),
        }

    async def ingest_inbound(
        self,
        *,
        organization_id: int,
        channel: Channel | str,
        body: str,
        phone: str | None = None,
        email: str | None = None,
        whatsapp_id: str | None = None,
        customer_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        channel = Channel(channel)
        conversations = get_conversation_service()
        identity, conversation = await conversations.get_or_open(
            organization_id=organization_id,
            channel=channel,
            phone=phone,
            email=email,
            whatsapp_id=whatsapp_id,
            customer_id=customer_id,
        )
        from api.db import db_client

        await db_client.update_conversation(
            conversation.id,
            organization_id=organization_id,
            waiting_for_reply=False,
            last_channel=channel.value,
        )
        message = await conversations.append(
            organization_id=organization_id,
            conversation_id=conversation.id,
            customer_id=identity.customer_id,
            channel=channel,
            direction="inbound",
            message_type="text",
            body=body,
            status="received",
            metadata=metadata,
        )
        return {
            "conversation_id": conversation.id,
            "customer_id": identity.customer_id,
            "message_id": message.id,
            "channel": channel.value,
        }

    def _target_channel(self, action: OrchestrationAction, origin: Channel) -> Channel:
        mapped = _ACTION_CHANNEL.get(action)
        if mapped:
            return mapped
        if origin in _RECEIPT_FALLBACK:
            return origin
        return Channel.SMS

    def _message_type(self, action: OrchestrationAction) -> str:
        return {
            OrchestrationAction.SEND_RECEIPT: "receipt",
            OrchestrationAction.SEND_DOCUMENT: "document",
            OrchestrationAction.START_CALL: "call",
            OrchestrationAction.ESCALATE: "escalation",
        }.get(action, "text")

    def _default_body(self, action: OrchestrationAction) -> str:
        return {
            OrchestrationAction.SEND_SMS: "Habari, this is a message from your service.",
            OrchestrationAction.SEND_WHATSAPP: "Habari, we are following up on WhatsApp.",
            OrchestrationAction.START_CALL: "Start outbound voice call",
            OrchestrationAction.SEND_RECEIPT: "Your payment receipt (KES) has been issued.",
            OrchestrationAction.SEND_DOCUMENT: "Please find the requested document.",
            OrchestrationAction.ESCALATE: "A teammate will take it from here.",
        }.get(action, "")


_orchestrator: ChannelOrchestrator | None = None


def get_channel_orchestrator() -> ChannelOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ChannelOrchestrator()
    return _orchestrator
