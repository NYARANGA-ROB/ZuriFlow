"""Default telephony gateway delegating to the existing provider registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from loguru import logger

from api.db import db_client
from api.enums import CallType
from api.services.quota_service import authorize_workflow_run_start
from api.services.telephony import registry as telephony_registry
from api.services.telephony.factory import get_telephony_provider_by_id
from api.services.voice_pipeline.telephony.interfaces import (
    InboundWebhookResult,
    TelephonyGateway,
    TelephonySession,
)
from api.services.voice_pipeline.types import InboundCallContext, VoicePipelineConfig
from api.utils.telephony_helper import normalize_webhook_data


@dataclass(frozen=True)
class ProviderInboundResponse:
    body: Any
    media_websocket_url: str | None = None


@dataclass
class RegistryTelephonySession:
    """Session adapter that forwards handshake to a registered TelephonyProvider."""

    provider_name: str
    _provider: Any = None
    _transport_kwargs: dict[str, Any] | None = None

    async def prepare(self, config: VoicePipelineConfig) -> None:
        from api.services.telephony.factory import get_telephony_provider_for_run

        workflow_run = await db_client.get_workflow_run(config.workflow_run_id)
        if not workflow_run:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        self._provider = await get_telephony_provider_for_run(
            workflow_run, config.organization_id
        )
        if self._provider.PROVIDER_NAME != self.provider_name:
            raise HTTPException(status_code=400, detail="Provider mismatch")

    async def handshake(self, websocket: Any) -> dict[str, Any]:
        if self._provider is None:
            raise RuntimeError("TelephonySession.prepare() must be called first")
        kwargs = await _extract_handshake_kwargs(
            self._provider, websocket, self.provider_name
        )
        self._transport_kwargs = kwargs
        return kwargs

    @property
    def transport_kwargs(self) -> dict[str, Any]:
        return dict(self._transport_kwargs or {})

    async def close(self, *, reason: str | None = None) -> None:
        logger.debug(
            f"Closing telephony session provider={self.provider_name} reason={reason}"
        )


class RegistryTelephonyGateway:
    """Routes inbound webhooks through the shared telephony DB + provider layer."""

    async def resolve_inbound(
        self,
        *,
        provider_name: str,
        webhook_data: dict[str, Any],
        headers: dict[str, str],
        raw_body: str,
        request_url: str,
    ) -> InboundCallContext:
        from api.routes.telephony import (
            _create_inbound_workflow_run,
            _detect_provider,
        )

        provider_class = await _detect_provider(webhook_data, headers)
        if not provider_class or provider_class.PROVIDER_NAME != provider_name:
            raise HTTPException(status_code=400, detail="provider_not_detected")

        normalized = normalize_webhook_data(provider_class, webhook_data)
        if normalized.direction != "inbound":
            raise HTTPException(status_code=400, detail="not_inbound")

        spec = telephony_registry.get_optional(provider_class.PROVIDER_NAME)
        account_field = spec.account_id_credential_field if spec else ""

        match = await db_client.find_inbound_route_by_account(
            provider=provider_class.PROVIDER_NAME,
            account_id_field=account_field,
            account_id=normalized.account_id or "",
            to_number=normalized.to_number,
            country_hint=normalized.to_country,
        )
        if not match:
            raise HTTPException(status_code=404, detail="inbound_route_not_found")

        config_row, phone_row = match
        if not phone_row.inbound_workflow_id:
            raise HTTPException(status_code=404, detail="workflow_not_assigned")

        workflow = await db_client.get_workflow(
            phone_row.inbound_workflow_id,
            organization_id=config_row.organization_id,
        )
        if not workflow:
            raise HTTPException(status_code=404, detail="workflow_not_found")

        provider_instance = await get_telephony_provider_by_id(
            config_row.id, config_row.organization_id
        )
        signature_valid = await provider_instance.verify_inbound_signature(
            request_url, webhook_data, headers, raw_body
        )
        if not signature_valid:
            raise HTTPException(status_code=401, detail="signature_invalid")

        workflow_run_id = await _create_inbound_workflow_run(
            phone_row.inbound_workflow_id,
            workflow.user_id,
            provider_class.PROVIDER_NAME,
            normalized,
            telephony_configuration_id=config_row.id,
            from_phone_number_id=phone_row.id,
        )
        quota = await authorize_workflow_run_start(
            workflow_id=phone_row.inbound_workflow_id,
            workflow_run_id=workflow_run_id,
        )
        if not quota.has_quota:
            raise HTTPException(status_code=402, detail=quota.error_message)

        return InboundCallContext(
            provider=provider_class.PROVIDER_NAME,
            call_id=normalized.call_id,
            workflow_id=phone_row.inbound_workflow_id,
            workflow_run_id=workflow_run_id,
            user_id=workflow.user_id,
            organization_id=config_row.organization_id,
            caller_number=normalized.from_number,
            called_number=normalized.to_number,
            telephony_configuration_id=config_row.id,
            metadata={"call_type": CallType.INBOUND.value},
        )

    async def build_inbound_response(
        self,
        *,
        context: InboundCallContext,
        websocket_url: str,
        backend_endpoint: str,
    ) -> InboundWebhookResult:
        provider = await get_telephony_provider_by_id(
            context.telephony_configuration_id,
            context.organization_id,
        )
        from api.utils.telephony_helper import normalize_webhook_data

        normalized = normalize_webhook_data(
            type(provider),
            {"CallSid": context.call_id, "From": context.caller_number, "To": context.called_number},
        )
        body = await provider.start_inbound_stream(
            websocket_url=websocket_url,
            workflow_run_id=context.workflow_run_id,
            normalized_data=normalized,
            backend_endpoint=backend_endpoint,
        )
        return ProviderInboundResponse(body=body, media_websocket_url=websocket_url)


async def _extract_handshake_kwargs(
    provider: Any, websocket: Any, provider_name: str
) -> dict[str, Any]:
    """Run provider handshake without starting the legacy pipeline."""
    import json

    if provider_name == "ari":
        return {}

    first = await websocket.receive_text()
    msg = json.loads(first)
    if msg.get("event") != "connected":
        raise ValueError("expected connected event")

    start_raw = await websocket.receive_text()
    start = json.loads(start_raw)
    if start.get("event") != "start":
        raise ValueError("expected start event")

    if provider_name == "twilio":
        return {
            "stream_sid": start["start"]["streamSid"],
            "call_sid": start["start"]["callSid"],
        }
    if provider_name == "telnyx":
        start_info = start.get("start", {})
        media_format = start_info.get("media_format") or {}
        return {
            "stream_id": start.get("stream_id", ""),
            "call_control_id": start_info.get("call_control_id", ""),
            "encoding": media_format.get("encoding") or "PCMU",
        }

    return {"raw_start": start}
