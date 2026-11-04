from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from api.services.whatsapp.types import InboundMessage, SendResult


class WhatsAppProvider(ABC):
    """Provider abstraction for Meta and Twilio WhatsApp APIs."""

    name: str

    @abstractmethod
    async def send_text(self, to_phone: str, body: str, **kwargs: Any) -> SendResult:
        raise NotImplementedError

    @abstractmethod
    async def send_template(
        self,
        to_phone: str,
        template_name: str,
        variables: dict[str, str],
        **kwargs: Any,
    ) -> SendResult:
        raise NotImplementedError

    @abstractmethod
    async def verify_webhook_signature(
        self,
        request_url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse_inbound_webhook(self, payload: dict[str, Any]) -> list[InboundMessage]:
        raise NotImplementedError

    @abstractmethod
    def parse_status_webhook(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError
