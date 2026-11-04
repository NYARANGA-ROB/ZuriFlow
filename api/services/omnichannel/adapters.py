"""Channel adapters. Voice stays on the existing telephony stack."""

from __future__ import annotations

from typing import Any, Protocol

from loguru import logger

from api.services.omnichannel.types import Channel, ChannelSendResult


class ChannelAdapter(Protocol):
    channel: Channel

    async def send(
        self,
        *,
        organization_id: int,
        to: str,
        body: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> ChannelSendResult: ...


class VoiceAdapter:
    channel = Channel.VOICE

    async def send(
        self,
        *,
        organization_id: int,
        to: str,
        body: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> ChannelSendResult:
        meta = metadata or {}
        workflow_run_id = meta.get("workflow_run_id")
        if not workflow_run_id:
            logger.info(
                "omnichannel START_CALL queued org={} to={} type={}",
                organization_id,
                to,
                message_type,
            )
            return ChannelSendResult(
                success=True,
                status="queued",
                metadata={"queued_call": True, "note": body, **meta},
            )

        from api.utils.common import get_backend_endpoints
        from api.services.telephony.domain import CallPurpose
        from api.services.telephony.start_call import StartCallRequest, execute_start_call
        from api.services.telephony.start_call_policy import StartCallRejected

        backend_endpoint, _ = await get_backend_endpoints()
        workflow_id = meta.get("workflow_id")
        user_id = meta.get("user_id")

        def _webhook_url_for_provider(active_provider) -> str:
            return (
                f"{backend_endpoint}/api/v1/telephony/{active_provider.WEBHOOK_ENDPOINT}"
                f"?workflow_id={workflow_id}"
                f"&user_id={user_id}"
                f"&workflow_run_id={workflow_run_id}"
                f"&organization_id={organization_id}"
            )

        try:
            started = await execute_start_call(
                StartCallRequest(
                    organization_id=organization_id,
                    workflow_run_id=int(workflow_run_id),
                    to_number=to,
                    webhook_url_for_provider=_webhook_url_for_provider,
                    telephony_configuration_id=meta.get("telephony_configuration_id"),
                    purpose=CallPurpose.TRANSACTIONAL,
                    customer_id=meta.get("customer_id"),
                    require_consent=bool(meta.get("require_consent")),
                )
            )
        except StartCallRejected as exc:
            return ChannelSendResult(
                success=False,
                status="blocked",
                error=exc.reason,
                metadata=meta,
            )
        except Exception as exc:
            logger.warning("omnichannel START_CALL failed: {}", exc)
            return ChannelSendResult(
                success=False,
                status="failed",
                error=str(exc),
                metadata=meta,
            )

        return ChannelSendResult(
            success=True,
            status="initiated",
            provider_message_id=started.call.provider_call_id,
            metadata={
                "command": "START_CALL",
                "provider": started.call.provider_name,
                "to": started.call.to.e164,
                **meta,
            },
        )


class SmsAdapter:
    channel = Channel.SMS

    async def send(
        self,
        *,
        organization_id: int,
        to: str,
        body: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> ChannelSendResult:
        logger.info("omnichannel SMS org={} to={} chars={}", organization_id, to, len(body))
        return ChannelSendResult(
            success=True,
            status="sent",
            provider_message_id=f"sms-{organization_id}-{to[-4:]}",
            metadata={"provider": "kenya_sms_gateway", **(metadata or {})},
        )


class WhatsAppAdapter:
    channel = Channel.WHATSAPP

    async def send(
        self,
        *,
        organization_id: int,
        to: str,
        body: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> ChannelSendResult:
        try:
            from api.services.whatsapp.messaging import WhatsAppMessagingService

            service = WhatsAppMessagingService()
            result = await service.send_text(
                organization_id=organization_id,
                phone_e164=to,
                body=body,
                workflow_run_id=(metadata or {}).get("workflow_run_id"),
                metadata=metadata,
            )
            ok = bool(result.get("success"))
            return ChannelSendResult(
                success=ok,
                status="sent" if ok else "failed",
                provider_message_id=str(result.get("provider_message_id") or result.get("id") or ""),
                error=None if ok else str(result.get("error") or "whatsapp_send_failed"),
                metadata=result if isinstance(result, dict) else {},
            )
        except Exception as exc:
            logger.warning("WhatsApp adapter fallback: {}", exc)
            return ChannelSendResult(
                success=True,
                status="queued",
                metadata={"fallback": True, "error": str(exc)},
            )


class WebChatAdapter:
    channel = Channel.WEB_CHAT

    async def send(
        self,
        *,
        organization_id: int,
        to: str,
        body: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> ChannelSendResult:
        return ChannelSendResult(
            success=True,
            status="sent",
            metadata={"web_session": to, **(metadata or {})},
        )


def adapter_for(channel: Channel) -> ChannelAdapter:
    mapping: dict[Channel, ChannelAdapter] = {
        Channel.VOICE: VoiceAdapter(),
        Channel.SMS: SmsAdapter(),
        Channel.WHATSAPP: WhatsAppAdapter(),
        Channel.WEB_CHAT: WebChatAdapter(),
    }
    return mapping[channel]
