"""Telephony service contracts for inbound call lifecycle."""

from __future__ import annotations

from typing import Any, Protocol

from api.services.voice_pipeline.types import InboundCallContext, VoicePipelineConfig


class InboundWebhookResult(Protocol):
    """HTTP response body returned to the carrier after inbound routing."""

    @property
    def body(self) -> Any: ...

    @property
    def media_websocket_url(self) -> str | None: ...


class TelephonyGateway(Protocol):
    """Accepts carrier webhooks and returns stream instructions."""

    async def resolve_inbound(
        self,
        *,
        provider_name: str,
        webhook_data: dict[str, Any],
        headers: dict[str, str],
        raw_body: str,
        request_url: str,
    ) -> InboundCallContext: ...

    async def build_inbound_response(
        self,
        *,
        context: InboundCallContext,
        websocket_url: str,
        backend_endpoint: str,
    ) -> InboundWebhookResult: ...


class TelephonySession(Protocol):
    """Active carrier media session bound to a workflow run."""

    async def prepare(self, config: VoicePipelineConfig) -> None:
        """Load credentials and validate session prerequisites."""

    async def handshake(self, websocket: Any) -> dict[str, Any]:
        """Provider-specific WebSocket handshake; returns transport kwargs."""

    async def close(self, *, reason: str | None = None) -> None: ...
