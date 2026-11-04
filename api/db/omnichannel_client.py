"""Database access for omnichannel identity, conversations, and follow-ups."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select, update

from api.db.base_client import BaseDBClient
from api.db.models import (
    CustomerCommunicationPreferenceModel,
    CustomerIdentityModel,
    EngagementConversationModel,
    EngagementFollowupRuleModel,
    EngagementMessageModel,
)


class OmnichannelClient(BaseDBClient):
    async def get_identity(
        self,
        *,
        organization_id: int,
        kind: str,
        value: str,
    ) -> CustomerIdentityModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerIdentityModel)
                .where(CustomerIdentityModel.organization_id == organization_id)
                .where(CustomerIdentityModel.kind == kind)
                .where(CustomerIdentityModel.value == value)
            )
            return result.scalars().first()

    async def list_identities_for_customer(
        self,
        *,
        organization_id: int,
        customer_id: int,
    ) -> list[CustomerIdentityModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerIdentityModel)
                .where(CustomerIdentityModel.organization_id == organization_id)
                .where(CustomerIdentityModel.customer_id == customer_id)
            )
            return list(result.scalars().all())

    async def upsert_identity(
        self,
        *,
        organization_id: int,
        customer_id: int,
        kind: str,
        value: str,
        is_primary: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerIdentityModel:
        existing = await self.get_identity(
            organization_id=organization_id, kind=kind, value=value
        )
        async with self.async_session() as session:
            if existing:
                existing.customer_id = customer_id
                existing.is_primary = is_primary or existing.is_primary
                if metadata:
                    existing.metadata_json = {**(existing.metadata_json or {}), **metadata}
                existing.updated_at = datetime.now(UTC)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return existing
            row = CustomerIdentityModel(
                organization_id=organization_id,
                customer_id=customer_id,
                kind=kind,
                value=value,
                is_primary=is_primary,
                metadata_json=metadata or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def reassign_identities(
        self,
        *,
        organization_id: int,
        from_customer_id: int,
        to_customer_id: int,
    ) -> int:
        async with self.async_session() as session:
            result = await session.execute(
                update(CustomerIdentityModel)
                .where(CustomerIdentityModel.organization_id == organization_id)
                .where(CustomerIdentityModel.customer_id == from_customer_id)
                .values(customer_id=to_customer_id, updated_at=datetime.now(UTC))
            )
            await session.commit()
            return result.rowcount or 0

    async def get_preferences(
        self,
        *,
        organization_id: int,
        customer_id: int,
    ) -> CustomerCommunicationPreferenceModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(CustomerCommunicationPreferenceModel)
                .where(CustomerCommunicationPreferenceModel.organization_id == organization_id)
                .where(CustomerCommunicationPreferenceModel.customer_id == customer_id)
            )
            return result.scalars().first()

    async def upsert_preferences(
        self,
        *,
        organization_id: int,
        customer_id: int,
        **fields: Any,
    ) -> CustomerCommunicationPreferenceModel:
        existing = await self.get_preferences(
            organization_id=organization_id, customer_id=customer_id
        )
        async with self.async_session() as session:
            if existing:
                for key, value in fields.items():
                    if key == "metadata" and value is not None:
                        existing.metadata_json = {**(existing.metadata_json or {}), **value}
                    elif hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                existing.updated_at = datetime.now(UTC)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return existing
            row = CustomerCommunicationPreferenceModel(
                organization_id=organization_id,
                customer_id=customer_id,
                **{k: v for k, v in fields.items() if k != "metadata" and hasattr(CustomerCommunicationPreferenceModel, k)},
                metadata_json=fields.get("metadata") or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_open_conversation(
        self,
        *,
        organization_id: int,
        customer_id: int | None,
        phone_e164: str | None,
    ) -> EngagementConversationModel | None:
        async with self.async_session() as session:
            stmt = (
                select(EngagementConversationModel)
                .where(EngagementConversationModel.organization_id == organization_id)
                .where(EngagementConversationModel.status == "open")
                .order_by(EngagementConversationModel.updated_at.desc())
            )
            if customer_id is not None:
                stmt = stmt.where(EngagementConversationModel.customer_id == customer_id)
            elif phone_e164:
                stmt = stmt.where(EngagementConversationModel.phone_e164 == phone_e164)
            else:
                return None
            result = await session.execute(stmt.limit(1))
            return result.scalars().first()

    async def create_conversation(
        self,
        *,
        organization_id: int,
        customer_id: int | None,
        phone_e164: str | None,
        origin_channel: str,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EngagementConversationModel:
        async with self.async_session() as session:
            row = EngagementConversationModel(
                organization_id=organization_id,
                customer_id=customer_id,
                phone_e164=phone_e164,
                origin_channel=origin_channel,
                last_channel=origin_channel,
                status="open",
                correlation_id=correlation_id,
                metadata_json=metadata or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def update_conversation(
        self,
        conversation_id: int,
        *,
        organization_id: int,
        **fields: Any,
    ) -> EngagementConversationModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(EngagementConversationModel)
                .where(EngagementConversationModel.id == conversation_id)
                .where(EngagementConversationModel.organization_id == organization_id)
            )
            row = result.scalars().first()
            if row is None:
                return None
            for key, value in fields.items():
                if hasattr(row, key) and value is not None:
                    setattr(row, key, value)
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return row

    async def add_message(
        self,
        *,
        organization_id: int,
        conversation_id: int,
        customer_id: int | None,
        channel: str,
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
    ) -> EngagementMessageModel:
        async with self.async_session() as session:
            row = EngagementMessageModel(
                organization_id=organization_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                channel=channel,
                direction=direction,
                message_type=message_type,
                body=body,
                status=status,
                provider_message_id=provider_message_id,
                workflow_run_id=workflow_run_id,
                transaction_id=transaction_id,
                consent_checked=consent_checked,
                consent_allowed=consent_allowed,
                metadata_json=metadata or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_conversation_messages(
        self,
        *,
        organization_id: int,
        conversation_id: int,
        limit: int = 200,
    ) -> list[EngagementMessageModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(EngagementMessageModel)
                .where(EngagementMessageModel.organization_id == organization_id)
                .where(EngagementMessageModel.conversation_id == conversation_id)
                .order_by(EngagementMessageModel.created_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def list_followup_rules(
        self,
        *,
        organization_id: int,
        trigger_event: str | None = None,
        enabled_only: bool = True,
    ) -> list[EngagementFollowupRuleModel]:
        async with self.async_session() as session:
            stmt = select(EngagementFollowupRuleModel).where(
                EngagementFollowupRuleModel.organization_id == organization_id
            )
            if trigger_event:
                stmt = stmt.where(EngagementFollowupRuleModel.trigger_event == trigger_event)
            if enabled_only:
                stmt = stmt.where(EngagementFollowupRuleModel.enabled.is_(True))
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_followup_rule(
        self,
        *,
        organization_id: int,
        trigger_event: str,
        action: str,
        channel: str | None,
        template_key: str | None,
        delay_seconds: int = 0,
        purpose: str = "transactional",
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> EngagementFollowupRuleModel:
        async with self.async_session() as session:
            row = EngagementFollowupRuleModel(
                organization_id=organization_id,
                trigger_event=trigger_event,
                action=action,
                channel=channel,
                template_key=template_key,
                delay_seconds=delay_seconds,
                purpose=purpose,
                enabled=enabled,
                metadata_json=metadata or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def engagement_metrics(
        self,
        *,
        organization_id: int,
        days: int = 30,
    ) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)
        async with self.async_session() as session:
            sent_expr = func.count(EngagementMessageModel.id)
            outbound = (
                select(
                    EngagementMessageModel.channel,
                    sent_expr.label("sent"),
                    func.sum(
                        case(
                            (EngagementMessageModel.status.in_(("delivered", "sent", "read")), 1),
                            else_=0,
                        )
                    ).label("delivered"),
                    func.sum(
                        case((EngagementMessageModel.status == "failed", 1), else_=0)
                    ).label("failed"),
                )
                .where(EngagementMessageModel.organization_id == organization_id)
                .where(EngagementMessageModel.direction == "outbound")
                .where(EngagementMessageModel.created_at >= since)
                .group_by(EngagementMessageModel.channel)
            )
            inbound = (
                select(
                    EngagementMessageModel.channel,
                    func.count(EngagementMessageModel.id).label("replies"),
                )
                .where(EngagementMessageModel.organization_id == organization_id)
                .where(EngagementMessageModel.direction == "inbound")
                .where(EngagementMessageModel.created_at >= since)
                .group_by(EngagementMessageModel.channel)
            )
            outbound_rows = (await session.execute(outbound)).all()
            inbound_rows = {
                row.channel: int(row.replies) for row in (await session.execute(inbound)).all()
            }

            conversions = await session.execute(
                select(
                    EngagementMessageModel.conversation_id,
                    EngagementMessageModel.channel,
                    EngagementMessageModel.message_type,
                    EngagementMessageModel.transaction_id,
                )
                .where(EngagementMessageModel.organization_id == organization_id)
                .where(EngagementMessageModel.created_at >= since)
            )
            conv_rows = conversions.all()

        by_channel = []
        total_sent = 0
        total_delivered = 0
        total_replies = 0
        for row in outbound_rows:
            sent = int(row.sent or 0)
            delivered = int(row.delivered or 0)
            replies = inbound_rows.get(row.channel, 0)
            total_sent += sent
            total_delivered += delivered
            total_replies += replies
            by_channel.append(
                {
                    "channel": row.channel,
                    "messages_sent": sent,
                    "delivered": delivered,
                    "failed": int(row.failed or 0),
                    "replies": replies,
                    "delivery_rate": (delivered / sent) if sent else 0.0,
                    "response_rate": (replies / sent) if sent else 0.0,
                }
            )

        per_conversation: dict[int, dict[str, bool]] = {}
        for row in conv_rows:
            bucket = per_conversation.setdefault(
                int(row.conversation_id),
                {"voice": False, "whatsapp": False, "payment": False},
            )
            if row.channel == "voice":
                bucket["voice"] = True
            if row.channel == "whatsapp":
                bucket["whatsapp"] = True
            if row.message_type == "receipt" or row.transaction_id:
                bucket["payment"] = True
        conversations = len(per_conversation)
        voice_to_wa = sum(1 for b in per_conversation.values() if b["voice"] and b["whatsapp"])
        payment_conversions = sum(1 for b in per_conversation.values() if b["payment"])

        return {
            "days": days,
            "messages_sent": total_sent,
            "delivery_rate": (total_delivered / total_sent) if total_sent else 0.0,
            "response_rate": (total_replies / total_sent) if total_sent else 0.0,
            "channel_conversion": {
                "conversations": conversations,
                "voice_to_whatsapp": voice_to_wa,
                "voice_to_whatsapp_rate": (voice_to_wa / conversations) if conversations else 0.0,
                "payment_conversions": payment_conversions,
                "payment_conversion_rate": (
                    payment_conversions / conversations if conversations else 0.0
                ),
            },
            "by_channel": by_channel,
        }
