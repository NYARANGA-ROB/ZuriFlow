from __future__ import annotations

from typing import Any

from sqlalchemy import desc
from sqlalchemy.future import select

from api.db.base_client import BaseDBClient
from api.db.models import WhatsAppConversationModel, WhatsAppMessageModel


class WhatsAppClient(BaseDBClient):
    async def get_or_create_conversation(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        provider: str,
        workflow_run_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WhatsAppConversationModel:
        async with self.async_session() as session:
            result = await session.execute(
                select(WhatsAppConversationModel)
                .where(WhatsAppConversationModel.organization_id == organization_id)
                .where(WhatsAppConversationModel.phone_e164 == phone_e164)
                .where(WhatsAppConversationModel.provider == provider)
                .with_for_update()
            )
            conversation = result.scalars().first()
            if conversation:
                if workflow_run_id and conversation.workflow_run_id is None:
                    conversation.workflow_run_id = workflow_run_id
                if metadata:
                    merged = dict(conversation.metadata_json or {})
                    merged.update(metadata)
                    conversation.metadata_json = merged
                await session.commit()
                await session.refresh(conversation)
                return conversation

            conversation = WhatsAppConversationModel(
                organization_id=organization_id,
                phone_e164=phone_e164,
                provider=provider,
                workflow_run_id=workflow_run_id,
                metadata_json=metadata or {},
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return conversation

    async def get_conversation(
        self,
        conversation_id: int,
        *,
        organization_id: int,
    ) -> WhatsAppConversationModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(WhatsAppConversationModel)
                .where(WhatsAppConversationModel.id == conversation_id)
                .where(WhatsAppConversationModel.organization_id == organization_id)
            )
            return result.scalars().first()

    async def list_conversations(
        self,
        *,
        organization_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WhatsAppConversationModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(WhatsAppConversationModel)
                .where(WhatsAppConversationModel.organization_id == organization_id)
                .order_by(desc(WhatsAppConversationModel.updated_at))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    async def append_message(
        self,
        *,
        conversation_id: int,
        direction: str,
        body: str,
        template_name: str | None = None,
        status: str = "pending",
        provider_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WhatsAppMessageModel:
        async with self.async_session() as session:
            result = await session.execute(
                select(WhatsAppConversationModel)
                .where(WhatsAppConversationModel.id == conversation_id)
                .with_for_update()
            )
            conversation = result.scalars().first()
            if not conversation:
                raise ValueError(f"WhatsApp conversation {conversation_id} not found")

            message = WhatsAppMessageModel(
                conversation_id=conversation_id,
                direction=direction,
                body=body,
                template_name=template_name,
                status=status,
                provider_message_id=provider_message_id,
                metadata_json=metadata or {},
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            try:
                from api.services.tenant_billing.hooks import on_whatsapp_message_recorded

                await on_whatsapp_message_recorded(
                    organization_id=conversation.organization_id,
                    message=message,
                )
            except Exception:
                pass

            return message

    async def update_message_status(
        self,
        *,
        message_id: int,
        status: str,
        provider_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WhatsAppMessageModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(WhatsAppMessageModel)
                .where(WhatsAppMessageModel.id == message_id)
                .with_for_update()
            )
            message = result.scalars().first()
            if not message:
                return None

            message.status = status
            if provider_message_id:
                message.provider_message_id = provider_message_id
            if metadata:
                merged = dict(message.metadata_json or {})
                merged.update(metadata)
                message.metadata_json = merged
            await session.commit()
            await session.refresh(message)
            return message

    async def list_messages(
        self,
        *,
        conversation_id: int,
        organization_id: int,
        limit: int = 100,
    ) -> list[WhatsAppMessageModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(WhatsAppMessageModel)
                .join(WhatsAppConversationModel)
                .where(WhatsAppMessageModel.conversation_id == conversation_id)
                .where(WhatsAppConversationModel.organization_id == organization_id)
                .order_by(WhatsAppMessageModel.created_at)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def mark_escalated(
        self,
        *,
        conversation_id: int,
        organization_id: int,
        reason: str | None = None,
    ) -> WhatsAppConversationModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(WhatsAppConversationModel)
                .where(WhatsAppConversationModel.id == conversation_id)
                .where(WhatsAppConversationModel.organization_id == organization_id)
                .with_for_update()
            )
            conversation = result.scalars().first()
            if not conversation:
                return None

            conversation.escalated = True
            conversation.status = "escalated"
            metadata = dict(conversation.metadata_json or {})
            if reason:
                metadata["escalation_reason"] = reason
            conversation.metadata_json = metadata
            await session.commit()
            await session.refresh(conversation)
            return conversation

    async def find_conversation_by_provider_message(
        self,
        *,
        organization_id: int,
        provider_message_id: str,
    ) -> tuple[WhatsAppConversationModel, WhatsAppMessageModel] | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(WhatsAppMessageModel, WhatsAppConversationModel)
                .join(WhatsAppConversationModel)
                .where(WhatsAppMessageModel.provider_message_id == provider_message_id)
                .where(WhatsAppConversationModel.organization_id == organization_id)
            )
            row = result.first()
            if not row:
                return None
            message, conversation = row
            return conversation, message
