"""Database operations for webhook subscriptions."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from api.db.base_client import BaseDBClient
from api.db.models import WebhookSubscriptionModel


class PublicApiClient(BaseDBClient):
    async def create_webhook_subscription(
        self,
        organization_id: int,
        *,
        name: str,
        url: str,
        events: list[str],
        secret: str,
    ) -> WebhookSubscriptionModel:
        async with self.async_session() as session:
            row = WebhookSubscriptionModel(
                organization_id=organization_id,
                subscription_uuid=f"whsub_{uuid.uuid4().hex}",
                name=name,
                url=url,
                secret=secret,
                events=events,
                is_active=True,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_webhook_subscriptions(
        self, organization_id: int, *, active_only: bool = True
    ) -> list[WebhookSubscriptionModel]:
        async with self.async_session() as session:
            query = select(WebhookSubscriptionModel).where(
                WebhookSubscriptionModel.organization_id == organization_id
            )
            if active_only:
                query = query.where(WebhookSubscriptionModel.is_active.is_(True))
            query = query.order_by(WebhookSubscriptionModel.created_at.desc())
            result = await session.execute(query)
            return list(result.scalars().all())

    async def list_webhook_subscriptions_for_event(
        self, organization_id: int, event_type: str
    ) -> list[WebhookSubscriptionModel]:
        rows = await self.list_webhook_subscriptions(organization_id, active_only=True)
        return [row for row in rows if event_type in (row.events or [])]

    async def get_webhook_subscription(
        self, organization_id: int, subscription_uuid: str
    ) -> Optional[WebhookSubscriptionModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(WebhookSubscriptionModel).where(
                    WebhookSubscriptionModel.organization_id == organization_id,
                    WebhookSubscriptionModel.subscription_uuid == subscription_uuid,
                )
            )
            return result.scalars().first()

    async def update_webhook_subscription(
        self,
        organization_id: int,
        subscription_uuid: str,
        *,
        name: str | None = None,
        url: str | None = None,
        events: list[str] | None = None,
        is_active: bool | None = None,
    ) -> Optional[WebhookSubscriptionModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(WebhookSubscriptionModel).where(
                    WebhookSubscriptionModel.organization_id == organization_id,
                    WebhookSubscriptionModel.subscription_uuid == subscription_uuid,
                )
            )
            row = result.scalars().first()
            if row is None:
                return None
            if name is not None:
                row.name = name
            if url is not None:
                row.url = url
            if events is not None:
                row.events = events
            if is_active is not None:
                row.is_active = is_active
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(row)
            return row

    async def delete_webhook_subscription(
        self, organization_id: int, subscription_uuid: str
    ) -> bool:
        async with self.async_session() as session:
            result = await session.execute(
                select(WebhookSubscriptionModel).where(
                    WebhookSubscriptionModel.organization_id == organization_id,
                    WebhookSubscriptionModel.subscription_uuid == subscription_uuid,
                )
            )
            row = result.scalars().first()
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def rotate_webhook_secret(
        self, organization_id: int, subscription_uuid: str
    ) -> tuple[Optional[WebhookSubscriptionModel], str]:
        secret = secrets.token_urlsafe(32)
        async with self.async_session() as session:
            result = await session.execute(
                select(WebhookSubscriptionModel).where(
                    WebhookSubscriptionModel.organization_id == organization_id,
                    WebhookSubscriptionModel.subscription_uuid == subscription_uuid,
                )
            )
            row = result.scalars().first()
            if row is None:
                return None, secret
            row.secret = secret
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(row)
            return row, secret
