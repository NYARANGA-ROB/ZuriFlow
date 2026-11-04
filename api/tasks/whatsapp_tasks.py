"""ARQ task for retrying failed WhatsApp outbound messages."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.services.whatsapp.messaging import WhatsAppMessagingService


async def send_whatsapp_message(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    service = WhatsAppMessagingService()
    result = await service.process_outbound_payload(payload)
    if not result.get("success"):
        logger.warning(
            "WhatsApp retry attempt {} failed: {}",
            payload.get("attempt", 1),
            result.get("error"),
        )
    return result
