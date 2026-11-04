"""Adapters for bridging legacy publishers to the platform event bus."""

from __future__ import annotations

import json
from typing import Any

from api.services.customer_timeline.correlation import resolve_customer_context
from api.services.platform_events.bus import get_platform_event_bus
from api.services.platform_events.schema import (
    PlatformEvent,
    PlatformEventSource,
    PlatformEventType,
)


async def _enrich_payload(
    organization_id: int,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    ctx = await resolve_customer_context(
        organization_id,
        phone_e164=payload.get("phone_e164"),
        workflow_run_id=payload.get("workflow_run_id"),
        transaction_id=payload.get("transaction_id"),
        customer_id=payload.get("customer_id"),
    )
    enriched = dict(payload)
    if ctx.get("phone_e164"):
        enriched["phone_e164"] = ctx["phone_e164"]
    if ctx.get("customer_id"):
        enriched["customer_id"] = ctx["customer_id"]
    return enriched, ctx.get("correlation_id")


async def publish_workflow_completed(
    *,
    organization_id: int,
    workflow_run_id: int,
    workflow_id: int | None = None,
    call_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "workflow_run_id": workflow_run_id,
        "workflow_id": workflow_id,
        "call_type": call_type,
    }
    if extra:
        payload.update(extra)

    payload, customer_correlation = await _enrich_payload(organization_id, payload)
    correlation_id = customer_correlation or f"workflow_run:{workflow_run_id}"

    workflow_event = PlatformEvent(
        event_type=PlatformEventType.WORKFLOW_COMPLETED,
        organization_id=organization_id,
        source=PlatformEventSource.WORKFLOW_COMPLETION,
        correlation_id=correlation_id,
        payload=payload,
        idempotency_key=f"workflow.completed:{workflow_run_id}",
    )
    result = await bus.publish(workflow_event)

    call_event = PlatformEvent(
        event_type=PlatformEventType.CALL_COMPLETED,
        organization_id=organization_id,
        source=PlatformEventSource.WORKFLOW_COMPLETION,
        correlation_id=correlation_id,
        payload=payload,
        idempotency_key=f"call.completed:{workflow_run_id}",
    )
    await bus.publish(call_event)
    return result


async def publish_payment_completed(
    *,
    organization_id: int,
    transaction_id: int,
    workflow_run_id: int | None = None,
    mpesa_receipt_number: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "transaction_id": transaction_id,
        "workflow_run_id": workflow_run_id,
        "mpesa_receipt_number": mpesa_receipt_number,
    }
    if extra:
        payload.update(extra)

    payload, customer_correlation = await _enrich_payload(organization_id, payload)

    event = PlatformEvent(
        event_type=PlatformEventType.PAYMENT_COMPLETED,
        organization_id=organization_id,
        source=PlatformEventSource.MPESA,
        correlation_id=customer_correlation or f"mpesa_txn:{transaction_id}",
        payload=payload,
        idempotency_key=f"payment.completed:{transaction_id}",
    )
    return await bus.publish(event)


async def publish_payment_failed(
    *,
    organization_id: int,
    transaction_id: int,
    workflow_run_id: int | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "transaction_id": transaction_id,
        "workflow_run_id": workflow_run_id,
        "reason": reason,
    }
    if extra:
        payload.update(extra)

    payload, customer_correlation = await _enrich_payload(organization_id, payload)

    event = PlatformEvent(
        event_type=PlatformEventType.PAYMENT_FAILED,
        organization_id=organization_id,
        source=PlatformEventSource.MPESA,
        correlation_id=customer_correlation or f"mpesa_txn:{transaction_id}",
        payload=payload,
        idempotency_key=f"payment.failed:{transaction_id}",
    )
    return await bus.publish(event)


async def publish_payment_initiated(
    *,
    organization_id: int,
    transaction_id: int,
    workflow_run_id: int | None = None,
    phone_e164: str | None = None,
    amount: float | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "transaction_id": transaction_id,
        "workflow_run_id": workflow_run_id,
        "phone_e164": phone_e164,
        "amount": amount,
    }
    payload, customer_correlation = await _enrich_payload(organization_id, payload)
    event = PlatformEvent(
        event_type=PlatformEventType.PAYMENT_INITIATED,
        organization_id=organization_id,
        source=PlatformEventSource.MPESA,
        correlation_id=customer_correlation or f"mpesa_txn:{transaction_id}",
        payload=payload,
        idempotency_key=f"payment.initiated:{transaction_id}",
    )
    return await bus.publish(event)


async def publish_whatsapp_message(
    *,
    organization_id: int,
    phone_e164: str,
    success: bool,
    conversation_id: int | None = None,
    message_id: int | None = None,
    workflow_run_id: int | None = None,
    template_name: str | None = None,
    body: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "phone_e164": phone_e164,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "workflow_run_id": workflow_run_id,
        "template_name": template_name,
        "body": body,
        "error": error,
    }
    payload, customer_correlation = await _enrich_payload(organization_id, payload)
    event_type = (
        PlatformEventType.WHATSAPP_MESSAGE_SENT
        if success
        else PlatformEventType.WHATSAPP_MESSAGE_FAILED
    )
    key_suffix = "sent" if success else "failed"
    idem = f"whatsapp.{key_suffix}:{message_id or conversation_id}:{workflow_run_id}"
    event = PlatformEvent(
        event_type=event_type,
        organization_id=organization_id,
        source=PlatformEventSource.WHATSAPP,
        correlation_id=customer_correlation,
        payload=payload,
        idempotency_key=idem,
    )
    return await bus.publish(event)


async def publish_campaign_event_from_json(
    raw_json: str,
    *,
    organization_id: int | None = None,
) -> dict[str, Any] | None:
    """Map legacy campaign pub/sub payloads onto platform events."""
    bus = get_platform_event_bus()
    if not bus.enabled:
        return None

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return None

    event_type_raw = str(data.get("type") or "")
    mapping = {
        "retry_needed": PlatformEventType.CAMPAIGN_RETRY_NEEDED,
        "batch_completed": PlatformEventType.CAMPAIGN_BATCH_COMPLETED,
        "campaign_completed": PlatformEventType.CAMPAIGN_COMPLETED,
    }
    mapped = mapping.get(event_type_raw)
    if mapped is None:
        return None

    campaign_id = data.get("campaign_id")
    if organization_id is None and campaign_id:
        try:
            from api.db import db_client

            campaign = await db_client.get_campaign(int(campaign_id))
            organization_id = campaign.organization_id if campaign else None
        except Exception:
            organization_id = None

    event = PlatformEvent(
        event_type=mapped,
        organization_id=organization_id,
        source=PlatformEventSource.CAMPAIGN,
        correlation_id=f"campaign:{campaign_id}" if campaign_id else None,
        payload=data,
        idempotency_key=f"campaign:{event_type_raw}:{campaign_id}:{data.get('timestamp')}",
    )
    return await bus.publish(event, route_async=True)


async def publish_orchestration_event(
    *,
    organization_id: int,
    orchestration_id: int,
    definition_name: str,
    orchestration_key: str,
    event_type: PlatformEventType,
    workflow_run_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "orchestration_id": orchestration_id,
        "definition_name": definition_name,
        "orchestration_key": orchestration_key,
        "workflow_run_id": workflow_run_id,
    }
    if extra:
        payload.update(extra)

    payload, customer_correlation = await _enrich_payload(organization_id, payload)
    idem_suffix = event_type.value.replace(".", "_")
    event = PlatformEvent(
        event_type=event_type,
        organization_id=organization_id,
        source=PlatformEventSource.DURABLE_EXECUTION,
        correlation_id=customer_correlation or f"orchestration:{orchestration_id}",
        payload=payload,
        idempotency_key=f"{idem_suffix}:{orchestration_id}:{(extra or {}).get('step_id', '')}",
    )
    return await bus.publish(event)


async def publish_escalation_created(
    *,
    organization_id: int,
    session_id: str,
    reason: str,
    phone_e164: str | None = None,
    workflow_run_id: int | None = None,
    customer_id: int | None = None,
    risk_level: str | None = None,
    queue_name: str | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "session_id": session_id,
        "reason": reason,
        "phone_e164": phone_e164,
        "workflow_run_id": workflow_run_id,
        "customer_id": customer_id,
        "risk_level": risk_level,
        "queue_name": queue_name,
    }
    payload, customer_correlation = await _enrich_payload(organization_id, payload)
    event = PlatformEvent(
        event_type=PlatformEventType.ESCALATION_CREATED,
        organization_id=organization_id,
        source=PlatformEventSource.SYSTEM,
        correlation_id=customer_correlation or f"escalation:{session_id}",
        payload=payload,
        idempotency_key=f"escalation.created:{session_id}",
    )
    return await bus.publish(event)


async def publish_escalation_resolved(
    *,
    organization_id: int,
    session_id: str,
    phone_e164: str | None = None,
    workflow_run_id: int | None = None,
    customer_id: int | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "session_id": session_id,
        "phone_e164": phone_e164,
        "workflow_run_id": workflow_run_id,
        "customer_id": customer_id,
    }
    payload, customer_correlation = await _enrich_payload(organization_id, payload)
    event = PlatformEvent(
        event_type=PlatformEventType.ESCALATION_RESOLVED,
        organization_id=organization_id,
        source=PlatformEventSource.SYSTEM,
        correlation_id=customer_correlation or f"escalation:{session_id}",
        payload=payload,
        idempotency_key=f"escalation.resolved:{session_id}",
    )
    return await bus.publish(event)


async def publish_email_message(
    *,
    organization_id: int,
    email: str,
    success: bool,
    phone_e164: str | None = None,
    customer_id: int | None = None,
    workflow_run_id: int | None = None,
    subject: str | None = None,
    body: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    bus = get_platform_event_bus()
    if not bus.enabled:
        return {"published": False}

    payload: dict[str, Any] = {
        "email": email,
        "phone_e164": phone_e164,
        "customer_id": customer_id,
        "workflow_run_id": workflow_run_id,
        "subject": subject,
        "body": body,
        "error": error,
    }
    payload, customer_correlation = await _enrich_payload(organization_id, payload)
    event_type = (
        PlatformEventType.EMAIL_SENT if success else PlatformEventType.EMAIL_FAILED
    )
    key_suffix = "sent" if success else "failed"
    event = PlatformEvent(
        event_type=event_type,
        organization_id=organization_id,
        source=PlatformEventSource.EMAIL,
        correlation_id=customer_correlation,
        payload=payload,
        idempotency_key=f"email.{key_suffix}:{email}:{workflow_run_id}",
    )
    return await bus.publish(event)
