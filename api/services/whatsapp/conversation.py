from __future__ import annotations

from typing import Any

from api.db import db_client
from api.db.models import WhatsAppConversationModel, WhatsAppMessageModel
from api.services.whatsapp.types import MessageDirection, MessageStatus


class WhatsAppConversationStore:
    """Persistent conversation storage backed by PostgreSQL."""

    async def get_or_create(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        provider: str,
        workflow_run_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WhatsAppConversationModel:
        return await db_client.get_or_create_conversation(
            organization_id=organization_id,
            phone_e164=phone_e164,
            provider=provider,
            workflow_run_id=workflow_run_id,
            metadata=metadata,
        )

    async def get(
        self,
        conversation_id: int,
        *,
        organization_id: int,
    ) -> WhatsAppConversationModel | None:
        return await db_client.get_conversation(
            conversation_id,
            organization_id=organization_id,
        )

    async def list_conversations(
        self,
        *,
        organization_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WhatsAppConversationModel]:
        return await db_client.list_conversations(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
        )

    async def record_outbound(
        self,
        *,
        conversation_id: int,
        body: str,
        template_name: str | None = None,
        status: MessageStatus = MessageStatus.PENDING,
        provider_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WhatsAppMessageModel:
        return await db_client.append_message(
            conversation_id=conversation_id,
            direction=MessageDirection.OUTBOUND.value,
            body=body,
            template_name=template_name,
            status=status.value,
            provider_message_id=provider_message_id,
            metadata=metadata,
        )

    async def record_inbound(
        self,
        *,
        conversation_id: int,
        body: str,
        provider_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WhatsAppMessageModel:
        return await db_client.append_message(
            conversation_id=conversation_id,
            direction=MessageDirection.INBOUND.value,
            body=body,
            status=MessageStatus.DELIVERED.value,
            provider_message_id=provider_message_id,
            metadata=metadata,
        )

    async def update_message_status(
        self,
        *,
        message_id: int,
        status: MessageStatus,
        provider_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WhatsAppMessageModel | None:
        return await db_client.update_message_status(
            message_id=message_id,
            status=status.value,
            provider_message_id=provider_message_id,
            metadata=metadata,
        )

    async def list_messages(
        self,
        *,
        conversation_id: int,
        organization_id: int,
        limit: int = 100,
    ) -> list[WhatsAppMessageModel]:
        return await db_client.list_messages(
            conversation_id=conversation_id,
            organization_id=organization_id,
            limit=limit,
        )

    async def mark_escalated(
        self,
        *,
        conversation_id: int,
        organization_id: int,
        reason: str | None = None,
    ) -> WhatsAppConversationModel | None:
        return await db_client.mark_escalated(
            conversation_id=conversation_id,
            organization_id=organization_id,
            reason=reason,
        )
