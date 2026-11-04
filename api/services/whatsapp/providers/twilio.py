from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import aiohttp
from loguru import logger
from twilio.request_validator import RequestValidator

from api.services.whatsapp.config import TwilioWhatsAppConfig
from api.services.whatsapp.providers.base import WhatsAppProvider
from api.services.whatsapp.types import InboundMessage, SendResult, WhatsAppProviderName
from api.utils.telephony_address import normalize_telephony_address


def _whatsapp_address(phone: str) -> str:
    normalized = normalize_telephony_address(phone)
    if normalized.startswith("whatsapp:"):
        return normalized
    return f"whatsapp:{normalized}"


class TwilioWhatsAppProvider(WhatsAppProvider):
    name = WhatsAppProviderName.TWILIO.value

    def __init__(self, config: TwilioWhatsAppConfig):
        self._config = config
        self._base = (
            f"https://api.twilio.com/2010-04-01/Accounts/{config.account_sid}/Messages.json"
        )
        self._validator = RequestValidator(config.auth_token)

    async def send_text(self, to_phone: str, body: str, **kwargs: Any) -> SendResult:
        data = {
            "To": _whatsapp_address(to_phone),
            "From": _whatsapp_address(self._config.from_number),
            "Body": body,
        }
        status_callback = kwargs.get("status_callback")
        if status_callback:
            data["StatusCallback"] = status_callback
        return await self._post_message(data)

    async def send_template(
        self,
        to_phone: str,
        template_name: str,
        variables: dict[str, str],
        **kwargs: Any,
    ) -> SendResult:
        # Twilio Content API templates are org-specific; fall back to rendered text.
        body = kwargs.get("rendered_body")
        if not body:
            parts = [f"{key}: {value}" for key, value in variables.items()]
            body = f"[{template_name}] " + " | ".join(parts)
        return await self.send_text(to_phone, body, **kwargs)

    async def _post_message(self, data: dict[str, str]) -> SendResult:
        auth = aiohttp.BasicAuth(self._config.account_sid, self._config.auth_token)
        try:
            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.post(
                    self._base,
                    data=urlencode(data),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status >= 400:
                        error = payload.get("message", str(payload))
                        return SendResult(success=False, error=error, raw_response=payload)
                    return SendResult(
                        success=True,
                        provider_message_id=payload.get("sid"),
                        raw_response=payload,
                    )
        except Exception as exc:
            logger.exception("Twilio WhatsApp send failed")
            return SendResult(success=False, error=str(exc))

    async def verify_webhook_signature(
        self,
        request_url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> bool:
        try:
            form = dict(json.loads(body.decode("utf-8"))) if body else {}
        except json.JSONDecodeError:
            from urllib.parse import parse_qs

            parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            form = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

        signature = headers.get("x-twilio-signature") or headers.get("X-Twilio-Signature")
        if not signature:
            return False
        return self._validator.validate(request_url, form, signature)

    def parse_inbound_webhook(self, payload: dict[str, Any]) -> list[InboundMessage]:
        body = payload.get("Body") or payload.get("body") or ""
        from_phone = payload.get("From") or payload.get("from") or ""
        from_phone = from_phone.replace("whatsapp:", "")
        if from_phone and not from_phone.startswith("+"):
            from_phone = f"+{from_phone}"
        return [
            InboundMessage(
                from_phone=from_phone,
                body=body,
                provider_message_id=payload.get("MessageSid") or payload.get("SmsMessageSid"),
                profile_name=payload.get("ProfileName"),
                raw_payload=payload,
            )
        ]

    def parse_status_webhook(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        status = (payload.get("MessageStatus") or payload.get("SmsStatus") or "").lower()
        if not status:
            return []
        return [
            {
                "provider_message_id": payload.get("MessageSid") or payload.get("SmsSid"),
                "status": status,
                "recipient": (payload.get("To") or "").replace("whatsapp:", ""),
                "raw": payload,
            }
        ]
