"""Unified conversation thread across channels."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.services.customer_timeline.correlation import customer_correlation_id, normalize_phone
from api.services.omnichannel.identity import get_customer_identity_service
from api.services.omnichannel.types import Channel


class ConversationService:
    async def get_or_open(
        self,
        *,
        organization_id: int,
        channel: Channel,
        phone: str | None = None,
        email: str | None = None,
        whatsapp_id: str | None = None,
        crm_id: str | None = None,
        customer_id: int | None = None,
        correlation_id: str | None = None,
    ):
        identity = await get_customer_identity_service().resolve(
            organization_id=organization_id,
            phone=phone,
            email=email,
            whatsapp_id=whatsapp_id,
            crm_id=crm_id,
            customer_id=customer_id,
        )
        phone_e164 = normalize_phone(phone) if phone else None
        conversation = await db_client.get_open_conversation(
            organization_id=organization_id,
            customer_id=identity.customer_id,
            phone_e164=phone_e164,
        )
        if conversation is None:
            conversation = await db_client.create_conversation(
                organization_id=organization_id,
                customer_id=identity.customer_id,
                phone_e164=phone_e164,
                origin_channel=channel.value,
                correlation_id=correlation_id
                or (customer_correlation_id(phone_e164) if phone_e164 else None),
            )
        return identity, conversation

    async def append(
        self,
        *,
        organization_id: int,
        conversation_id: int,
        customer_id: int | None,
        channel: Channel,
        direction: str,
        message_type: str,
        body: str | None,
        status: str,
        provider_message_id: str | None = None,
        workflow_run_id: int | None = None,
        transaction_id: int | None = None,
        consent_checked: bool = True,
        consent_allowed: bool = True,
        metadata: dict[str, Any] | None = None,
    ):
        message = await db_client.add_message(
            organization_id=organization_id,
            conversation_id=conversation_id,
            customer_id=customer_id,
            channel=channel.value,
            direction=direction,
            message_type=message_type,
            body=body,
            status=status,
            provider_message_id=provider_message_id,
            workflow_run_id=workflow_run_id,
            transaction_id=transaction_id,
            consent_checked=consent_checked,
            consent_allowed=consent_allowed,
            metadata=metadata,
        )
        await db_client.update_conversation(
            conversation_id,
            organization_id=organization_id,
            last_channel=channel.value,
            waiting_for_reply=direction == "outbound",
            customer_id=customer_id,
        )
        return message

    async def timeline(
        self,
        *,
        organization_id: int,
        conversation_id: int,
    ) -> dict[str, Any]:
        messages = await db_client.list_conversation_messages(
            organization_id=organization_id,
            conversation_id=conversation_id,
        )
        return {
            "conversation_id": conversation_id,
            "organization_id": organization_id,
            "messages": [
                {
                    "id": m.id,
                    "channel": m.channel,
                    "direction": m.direction,
                    "message_type": m.message_type,
                    "body": m.body,
                    "status": m.status,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "transaction_id": m.transaction_id,
                    "workflow_run_id": m.workflow_run_id,
                }
                for m in messages
            ],
        }


_conversations: ConversationService | None = None


def get_conversation_service() -> ConversationService:
    global _conversations
    if _conversations is None:
        _conversations = ConversationService()
    return _conversations
