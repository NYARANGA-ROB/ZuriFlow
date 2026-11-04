"""WhatsApp webhook handlers and authenticated messaging routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from loguru import logger

from api.db import db_client
from api.db.models import UserModel
from api.schemas.whatsapp import (
    EscalateConversationRequest,
    PostCallSummaryRequest,
    SendAppointmentRequest,
    SendCallSummaryRequest,
    SendMessageResult,
    SendPaymentLinkRequest,
    WhatsAppConversationResponse,
    WhatsAppMessageResponse,
)
from api.services.auth.depends import get_user
from api.services.tenant import get_tenant_context
from api.services.tenant.types import TenantContext
from api.services.whatsapp.config import WhatsAppOrgConfig
from api.services.whatsapp.conversation import WhatsAppConversationStore
from api.services.whatsapp.escalation import WhatsAppEscalationService
from api.services.whatsapp.integration import run_post_call_whatsapp_workflow
from api.services.whatsapp.messaging import WhatsAppMessagingService
from api.services.whatsapp.providers.factory import get_whatsapp_provider
from api.services.whatsapp.types import MessageStatus, WhatsAppProviderName

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


async def get_organization_id(ctx: TenantContext = Depends(get_tenant_context)) -> int:
    return ctx.organization_id


def _conversation_response(conversation, messages=None) -> WhatsAppConversationResponse:
    return WhatsAppConversationResponse(
        id=conversation.id,
        phone_e164=conversation.phone_e164,
        provider=conversation.provider,
        workflow_run_id=conversation.workflow_run_id,
        status=conversation.status,
        escalated=conversation.escalated,
        metadata=conversation.metadata_json or {},
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            WhatsAppMessageResponse(
                id=m.id,
                direction=m.direction,
                body=m.body,
                template_name=m.template_name,
                status=m.status,
                provider_message_id=m.provider_message_id,
                created_at=m.created_at,
            )
            for m in (messages or [])
        ],
    )


@router.post("/send/summary", response_model=SendMessageResult)
async def send_summary(
    body: SendCallSummaryRequest,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    service = WhatsAppMessagingService()
    result = await service.send_call_summary(
        organization_id=organization_id,
        phone_e164=body.phone_e164,
        customer_name=body.customer_name,
        summary=body.summary,
        intent=body.intent,
        next_steps=body.next_steps,
        workflow_run_id=body.workflow_run_id,
        provider=body.provider,
    )
    return SendMessageResult(**result)


@router.post("/send/payment-link", response_model=SendMessageResult)
async def send_payment_link(
    body: SendPaymentLinkRequest,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    service = WhatsAppMessagingService()
    result = await service.send_payment_link(
        organization_id=organization_id,
        phone_e164=body.phone_e164,
        customer_name=body.customer_name,
        amount=body.amount,
        payment_url=body.payment_url,
        reference=body.reference,
        workflow_run_id=body.workflow_run_id,
        provider=body.provider,
    )
    return SendMessageResult(**result)


@router.post("/send/appointment", response_model=SendMessageResult)
async def send_appointment(
    body: SendAppointmentRequest,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    service = WhatsAppMessagingService()
    result = await service.send_appointment_confirmation(
        organization_id=organization_id,
        phone_e164=body.phone_e164,
        customer_name=body.customer_name,
        appointment_date=body.appointment_date,
        appointment_time=body.appointment_time,
        location=body.location,
        workflow_run_id=body.workflow_run_id,
        provider=body.provider,
    )
    return SendMessageResult(**result)


@router.post("/post-call-summary", response_model=SendMessageResult)
async def post_call_summary(
    body: PostCallSummaryRequest,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    from api.services.whatsapp.integration import send_post_call_whatsapp_summary

    result = await send_post_call_whatsapp_summary(
        organization_id=organization_id,
        phone_e164=body.phone_e164,
        workflow_run_id=body.workflow_run_id,
        memory_snapshot=body.memory_snapshot,
        gathered_context=body.gathered_context,
        customer_name=body.customer_name,
    )
    return SendMessageResult(
        success=result.get("success", False),
        conversation_id=result.get("conversation_id"),
        error=result.get("skip_reason"),
    )


@router.get("/conversations", response_model=list[WhatsAppConversationResponse])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    store = WhatsAppConversationStore()
    conversations = await store.list_conversations(
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )
    return [_conversation_response(c) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=WhatsAppConversationResponse)
async def get_conversation(
    conversation_id: int,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    store = WhatsAppConversationStore()
    conversation = await store.get(conversation_id, organization_id=organization_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await store.list_messages(
        conversation_id=conversation_id,
        organization_id=organization_id,
    )
    return _conversation_response(conversation, messages)


@router.post("/conversations/{conversation_id}/escalate")
async def escalate_conversation(
    conversation_id: int,
    body: EscalateConversationRequest,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    messaging = WhatsAppMessagingService()
    escalation = WhatsAppEscalationService()
    return await escalation.escalate(
        messaging,
        organization_id=organization_id,
        conversation_id=conversation_id,
        reason=body.reason,
        context=body.context,
        customer_phone=body.customer_phone,
    )


async def _load_config(organization_id: int) -> WhatsAppOrgConfig:
    service = WhatsAppMessagingService()
    config = await service.load_org_config(organization_id)
    if not config.enabled:
        raise HTTPException(status_code=403, detail="WhatsApp is disabled")
    return config


def _map_provider_status(status: str) -> MessageStatus:
    mapping = {
        "sent": MessageStatus.SENT,
        "delivered": MessageStatus.DELIVERED,
        "read": MessageStatus.READ,
        "failed": MessageStatus.FAILED,
        "undelivered": MessageStatus.FAILED,
    }
    return mapping.get(status.lower(), MessageStatus.SENT)


@router.get("/webhooks/meta/{organization_id}")
async def meta_webhook_verify(
    organization_id: int,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    config = await _load_config(organization_id)
    if not config.meta:
        raise HTTPException(status_code=400, detail="Meta WhatsApp not configured")
    provider = get_whatsapp_provider(WhatsAppProviderName.META.value, config)
    challenge = provider.verify_subscription(hub_mode, hub_verify_token, hub_challenge)
    if challenge is None:
        raise HTTPException(status_code=403, detail="Verification failed")
    return Response(content=challenge, media_type="text/plain")


@router.post("/webhooks/meta/{organization_id}")
async def meta_webhook_inbound(organization_id: int, request: Request):
    config = await _load_config(organization_id)
    body = await request.body()
    provider = get_whatsapp_provider(WhatsAppProviderName.META.value, config)
    if not await provider.verify_webhook_signature(
        str(request.url), body, dict(request.headers)
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body.decode("utf-8"))
    messaging = WhatsAppMessagingService()
    results: list[dict[str, Any]] = []
    for inbound in provider.parse_inbound_webhook(payload):
        results.append(
            await messaging.handle_inbound(
                organization_id=organization_id,
                provider_name=WhatsAppProviderName.META.value,
                inbound=inbound,
            )
        )

    for status_event in provider.parse_status_webhook(payload):
        await _apply_status_update(organization_id, status_event)

    return {"status": "ok", "processed": len(results)}


@router.post("/webhooks/twilio/{organization_id}")
async def twilio_webhook_inbound(organization_id: int, request: Request):
    config = await _load_config(organization_id)
    form = await request.form()
    payload = dict(form)
    provider = get_whatsapp_provider(WhatsAppProviderName.TWILIO.value, config)
    signature = request.headers.get("x-twilio-signature") or request.headers.get(
        "X-Twilio-Signature"
    )
    if not signature or not provider._validator.validate(
        str(request.url), payload, signature
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    messaging = WhatsAppMessagingService()
    results: list[dict[str, Any]] = []

    if payload.get("Body"):
        for inbound in provider.parse_inbound_webhook(payload):
            results.append(
                await messaging.handle_inbound(
                    organization_id=organization_id,
                    provider_name=WhatsAppProviderName.TWILIO.value,
                    inbound=inbound,
                )
            )

    for status_event in provider.parse_status_webhook(payload):
        await _apply_status_update(organization_id, status_event)

    return {"status": "ok", "processed": len(results)}


async def _apply_status_update(organization_id: int, status_event: dict[str, Any]) -> None:
    provider_message_id = status_event.get("provider_message_id")
    if not provider_message_id:
        return
    match = await db_client.find_conversation_by_provider_message(
        organization_id=organization_id,
        provider_message_id=provider_message_id,
    )
    if not match:
        logger.debug(
            "WhatsApp status for unknown message {} org={}",
            provider_message_id,
            organization_id,
        )
        return
    _conversation, message = match
    status = _map_provider_status(status_event.get("status", ""))
    await db_client.update_message_status(
        message_id=message.id,
        status=status.value,
        metadata={"status_event": status_event},
    )
