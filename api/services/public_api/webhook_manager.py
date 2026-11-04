"""Webhook subscription management and signed delivery."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from loguru import logger

from api.constants import APP_NAME, PUBLIC_API_WEBHOOK_DELIVERY_TIMEOUT_S
from api.db import db_client
from api.db.models import WebhookSubscriptionModel
from api.services.public_api.types import (
    WebhookDeliveryResult,
    WebhookEventType,
    WebhookPayload,
)


class WebhookManager:
    async def list_subscriptions(
        self, organization_id: int, *, active_only: bool = True
    ) -> list[WebhookSubscriptionModel]:
        return await db_client.list_webhook_subscriptions(
            organization_id, active_only=active_only
        )

    async def create_subscription(
        self,
        organization_id: int,
        *,
        name: str,
        url: str,
        events: list[str],
    ) -> tuple[WebhookSubscriptionModel, str]:
        secret = secrets.token_urlsafe(32)
        subscription = await db_client.create_webhook_subscription(
            organization_id=organization_id,
            name=name,
            url=url,
            events=events,
            secret=secret,
        )
        return subscription, secret

    async def update_subscription(
        self,
        organization_id: int,
        subscription_uuid: str,
        *,
        name: str | None = None,
        url: str | None = None,
        events: list[str] | None = None,
        is_active: bool | None = None,
    ) -> WebhookSubscriptionModel:
        updated = await db_client.update_webhook_subscription(
            organization_id,
            subscription_uuid,
            name=name,
            url=url,
            events=events,
            is_active=is_active,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Webhook subscription not found")
        return updated

    async def delete_subscription(
        self, organization_id: int, subscription_uuid: str
    ) -> bool:
        deleted = await db_client.delete_webhook_subscription(
            organization_id, subscription_uuid
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Webhook subscription not found")
        return True

    async def get_subscription(
        self, organization_id: int, subscription_uuid: str
    ) -> WebhookSubscriptionModel:
        row = await db_client.get_webhook_subscription(organization_id, subscription_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="Webhook subscription not found")
        return row

    async def deliver_test_event(
        self, organization_id: int, subscription_uuid: str
    ) -> WebhookDeliveryResult:
        subscription = await self.get_subscription(organization_id, subscription_uuid)
        payload = WebhookPayload(
            id=f"evt_{uuid.uuid4().hex}",
            type=WebhookEventType.WORKFLOW_RUN_COMPLETED.value,
            created_at=datetime.now(timezone.utc).isoformat(),
            organization_id=organization_id,
            data={
                "test": True,
                "message": f"{APP_NAME} webhook test delivery",
                "subscription_uuid": subscription_uuid,
            },
        )
        return await self._deliver(subscription, payload)

    async def emit_event(
        self,
        organization_id: int,
        event_type: WebhookEventType | str,
        data: dict[str, Any],
    ) -> list[WebhookDeliveryResult]:
        event_value = (
            event_type.value if isinstance(event_type, WebhookEventType) else event_type
        )
        subscriptions = await db_client.list_webhook_subscriptions_for_event(
            organization_id, event_value
        )
        if not subscriptions:
            return []

        payload = WebhookPayload(
            id=f"evt_{uuid.uuid4().hex}",
            type=event_value,
            created_at=datetime.now(timezone.utc).isoformat(),
            organization_id=organization_id,
            data=data,
        )
        results: list[WebhookDeliveryResult] = []
        for subscription in subscriptions:
            results.append(await self._deliver(subscription, payload))
        return results

    async def _deliver(
        self,
        subscription: WebhookSubscriptionModel,
        payload: WebhookPayload,
    ) -> WebhookDeliveryResult:
        body = json.dumps(
            {
                "id": payload.id,
                "type": payload.type,
                "created_at": payload.created_at,
                "organization_id": payload.organization_id,
                "data": payload.data,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        timestamp = str(int(time.time()))
        signature = sign_webhook_payload(subscription.secret, timestamp, body)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"{APP_NAME}-Webhooks/1.0",
            "X-Dograh-Event": payload.type,
            "X-Dograh-Delivery": payload.id,
            "X-Dograh-Timestamp": timestamp,
            "X-Dograh-Signature": signature,
        }

        try:
            async with httpx.AsyncClient(
                timeout=PUBLIC_API_WEBHOOK_DELIVERY_TIMEOUT_S
            ) as client:
                response = await client.post(subscription.url, content=body, headers=headers)
            success = 200 <= response.status_code < 300
            if not success:
                logger.warning(
                    f"Webhook delivery failed for {subscription.subscription_uuid}: "
                    f"status={response.status_code}"
                )
            return WebhookDeliveryResult(
                subscription_uuid=subscription.subscription_uuid,
                success=success,
                status_code=response.status_code,
                response_body=response.text[:500],
            )
        except Exception as exc:
            logger.warning(
                f"Webhook delivery error for {subscription.subscription_uuid}: {exc}"
            )
            return WebhookDeliveryResult(
                subscription_uuid=subscription.subscription_uuid,
                success=False,
                error=str(exc),
            )


def sign_webhook_payload(secret: str, timestamp: str, body: str) -> str:
    signed = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={signed}"


def verify_webhook_signature(
    secret: str, timestamp: str, body: str, signature: str
) -> bool:
    expected = sign_webhook_payload(secret, timestamp, body)
    return hmac.compare_digest(expected, signature)


def get_webhook_manager() -> WebhookManager:
    return WebhookManager()
