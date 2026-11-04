from __future__ import annotations

import json
import time
from typing import Any

import httpx
import redis.asyncio as aioredis
from loguru import logger

from api.constants import REDIS_URL
from api.services.call_routing.config import CallRoutingOrgConfig, EscalationRoutingConfig
from api.services.call_routing.i18n import escalation_ack
from api.services.call_routing.types import EscalationRequest


class CallEscalationManager:
    """Escalate voice calls to human agents via transfer, webhook, or notify."""

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _pending_key(session_id: str) -> str:
        return f"call_routing:escalation:{session_id}"

    async def escalate(
        self,
        request: EscalationRequest,
        *,
        org_config: CallRoutingOrgConfig,
    ) -> dict[str, Any]:
        esc = org_config.escalation
        ack = escalation_ack(request.language)

        payload = {
            **request.to_dict(),
            "transfer_destination": request.transfer_destination or esc.transfer_destination,
            "auto_transfer": esc.auto_transfer,
            "created_at": time.time(),
            "status": "pending",
        }

        redis = await self._get_redis()
        await redis.setex(
            self._pending_key(request.session_id),
            600,
            json.dumps(payload),
        )

        webhook_ok = False
        if esc.webhook_url:
            webhook_ok = await self._notify_webhook(esc.webhook_url, payload)

        whatsapp_notified = False
        if esc.notify_numbers and request.phone_e164:
            whatsapp_notified = await self._notify_via_whatsapp(
                organization_id=request.organization_id,
                notify_numbers=esc.notify_numbers,
                request=request,
            )

        return {
            "session_id": request.session_id,
            "escalated": True,
            "voice_prompt": ack,
            "pending_transfer": bool(payload["transfer_destination"] and esc.auto_transfer),
            "transfer_destination": payload["transfer_destination"],
            "webhook_notified": webhook_ok,
            "whatsapp_notified": whatsapp_notified,
        }

    async def get_pending(self, session_id: str) -> dict[str, Any] | None:
        redis = await self._get_redis()
        raw = await redis.get(self._pending_key(session_id))
        return json.loads(raw) if raw else None

    async def clear_pending(self, session_id: str) -> None:
        redis = await self._get_redis()
        await redis.delete(self._pending_key(session_id))

    async def _notify_webhook(self, url: str, payload: dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code >= 400:
                    logger.warning(
                        "call routing escalation webhook failed: {} {}",
                        response.status_code,
                        response.text,
                    )
                    return False
                return True
        except Exception:
            logger.exception("call routing escalation webhook error")
            return False

    async def _notify_via_whatsapp(
        self,
        *,
        organization_id: int,
        notify_numbers: tuple[str, ...],
        request: EscalationRequest,
    ) -> bool:
        try:
            from api.services.whatsapp.messaging import WhatsAppMessagingService

            messaging = WhatsAppMessagingService()
            body = (
                f"Voice escalation: {request.intent}\n"
                f"Customer: {request.phone_e164 or 'unknown'}\n"
                f"Reason: {request.reason}\n"
                f"Session: {request.session_id}"
            )
            sent = False
            for phone in notify_numbers:
                result = await messaging.send_text(
                    organization_id=organization_id,
                    phone_e164=phone,
                    body=body,
                    workflow_run_id=request.workflow_run_id,
                    metadata={"call_routing_escalation": True, "session_id": request.session_id},
                )
                sent = sent or bool(result.get("success"))
            return sent
        except Exception:
            logger.exception("call routing WhatsApp escalation notify failed")
            return False
