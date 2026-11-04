from __future__ import annotations

import hashlib
import hmac
from typing import Any

from api.services.http_sessions import get_shared_http_session
from api.services.kenya_production.resilience import whatsapp_circuit

from api.services.whatsapp.config import MetaWhatsAppConfig
from api.services.whatsapp.providers.base import WhatsAppProvider
from api.services.whatsapp.types import InboundMessage, SendResult, WhatsAppProviderName
from api.utils.telephony_address import normalize_telephony_address


class MetaWhatsAppProvider(WhatsAppProvider):
    name = WhatsAppProviderName.META.value

    def __init__(self, config: MetaWhatsAppConfig):
        self._config = config
        self._base = (
            f"https://graph.facebook.com/{config.api_version}/{config.phone_number_id}"
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.access_token}",
            "Content-Type": "application/json",
        }

    def _normalize_to(self, phone: str) -> str:
        normalized = normalize_telephony_address(phone)
        return normalized.lstrip("+")

    async def send_text(self, to_phone: str, body: str, **kwargs: Any) -> SendResult:
        payload = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to_phone),
            "type": "text",
            "text": {"body": body},
        }
        return await self._post_message(payload)

    async def send_template(
        self,
        to_phone: str,
        template_name: str,
        variables: dict[str, str],
        **kwargs: Any,
    ) -> SendResult:
        components = []
        if variables:
            components.append(
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(value)}
                        for value in variables.values()
                    ],
                }
            )
        payload = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to_phone),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": kwargs.get("language_code", "en")},
                "components": components,
            },
        }
        return await self._post_message(payload)

    async def _post_message(self, payload: dict[str, Any]) -> SendResult:
        url = f"{self._base}/messages"
        breaker = whatsapp_circuit()
        if not breaker.allow():
            return SendResult(success=False, error="WhatsApp circuit open — backing off")
        try:
            session = await get_shared_http_session()
            async with session.post(
                url, headers=self._headers(), json=payload
            ) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    breaker.record_failure()
                    error = data.get("error", {}).get("message", str(data))
                    return SendResult(success=False, error=error, raw_response=data)
                breaker.record_success()
                message_id = (data.get("messages") or [{}])[0].get("id")
                return SendResult(
                    success=True,
                    provider_message_id=message_id,
                    raw_response=data,
                )
        except Exception as exc:
            breaker.record_failure()
            logger.exception("Meta WhatsApp send failed")
            return SendResult(success=False, error=str(exc))

    async def verify_webhook_signature(
        self,
        request_url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> bool:
        secret = self._config.app_secret
        if not secret:
            return False
        signature = headers.get("x-hub-signature-256") or headers.get(
            "X-Hub-Signature-256"
        )
        if not signature or not signature.startswith("sha256="):
            return False
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature[7:], expected)

    def parse_inbound_webhook(self, payload: dict[str, Any]) -> list[InboundMessage]:
        messages: list[InboundMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for item in value.get("messages", []):
                    if item.get("type") != "text":
                        continue
                    from_phone = item.get("from", "")
                    body = (item.get("text") or {}).get("body", "")
                    profile = None
                    contacts = value.get("contacts") or []
                    if contacts:
                        profile = contacts[0].get("profile", {}).get("name")
                    messages.append(
                        InboundMessage(
                            from_phone=f"+{from_phone}" if from_phone and not from_phone.startswith("+") else from_phone,
                            body=body,
                            provider_message_id=item.get("id"),
                            profile_name=profile,
                            raw_payload=item,
                        )
                    )
        return messages

    def parse_status_webhook(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for item in value.get("statuses", []):
                    statuses.append(
                        {
                            "provider_message_id": item.get("id"),
                            "status": item.get("status"),
                            "recipient": item.get("recipient_id"),
                            "raw": item,
                        }
                    )
        return statuses

    def verify_subscription(self, mode: str, token: str, challenge: str) -> str | None:
        if mode == "subscribe" and token == self._config.verify_token:
            return challenge
        return None
