"""Index platform events into the customer timeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from api.services.customer_timeline.correlation import resolve_customer_context
from api.services.customer_timeline.state_machine import derive_journey_state
from api.services.customer_timeline.types import CustomerJourneyState, TimelineChannel
from api.services.platform_events.schema import PlatformEvent, PlatformEventType


_EVENT_CHANNEL: dict[PlatformEventType, TimelineChannel] = {
    PlatformEventType.CALL_COMPLETED: TimelineChannel.VOICE,
    PlatformEventType.CALL_FAILED: TimelineChannel.VOICE,
    PlatformEventType.WORKFLOW_COMPLETED: TimelineChannel.VOICE,
    PlatformEventType.WORKFLOW_TIMEOUT: TimelineChannel.VOICE,
    PlatformEventType.PAYMENT_INITIATED: TimelineChannel.PAYMENT,
    PlatformEventType.PAYMENT_COMPLETED: TimelineChannel.PAYMENT,
    PlatformEventType.PAYMENT_FAILED: TimelineChannel.PAYMENT,
    PlatformEventType.PAYMENT_TIMEOUT: TimelineChannel.PAYMENT,
    PlatformEventType.CAMPAIGN_RETRY_NEEDED: TimelineChannel.CAMPAIGN,
    PlatformEventType.CAMPAIGN_BATCH_COMPLETED: TimelineChannel.CAMPAIGN,
    PlatformEventType.CAMPAIGN_COMPLETED: TimelineChannel.CAMPAIGN,
    PlatformEventType.ESCALATION_CREATED: TimelineChannel.ESCALATION,
    PlatformEventType.ESCALATION_RESOLVED: TimelineChannel.ESCALATION,
    PlatformEventType.WHATSAPP_MESSAGE_SENT: TimelineChannel.WHATSAPP,
    PlatformEventType.WHATSAPP_MESSAGE_FAILED: TimelineChannel.WHATSAPP,
    PlatformEventType.EMAIL_SENT: TimelineChannel.EMAIL,
    PlatformEventType.EMAIL_FAILED: TimelineChannel.EMAIL,
    PlatformEventType.ORCHESTRATION_STARTED: TimelineChannel.ORCHESTRATION,
    PlatformEventType.ORCHESTRATION_SIGNAL: TimelineChannel.ORCHESTRATION,
    PlatformEventType.ORCHESTRATION_COMPLETED: TimelineChannel.ORCHESTRATION,
    PlatformEventType.ORCHESTRATION_FAILED: TimelineChannel.ORCHESTRATION,
}

_EVENT_JOURNEY: dict[PlatformEventType, CustomerJourneyState] = {
    PlatformEventType.CALL_COMPLETED: CustomerJourneyState.VOICE_COMPLETED,
    PlatformEventType.WORKFLOW_COMPLETED: CustomerJourneyState.VOICE_COMPLETED,
    PlatformEventType.PAYMENT_INITIATED: CustomerJourneyState.PAYMENT_PENDING,
    PlatformEventType.PAYMENT_COMPLETED: CustomerJourneyState.PAYMENT_COMPLETED,
    PlatformEventType.PAYMENT_FAILED: CustomerJourneyState.PAYMENT_FAILED,
    PlatformEventType.WHATSAPP_MESSAGE_SENT: CustomerJourneyState.WHATSAPP_FOLLOW_UP,
    PlatformEventType.EMAIL_SENT: CustomerJourneyState.EMAIL_FOLLOW_UP,
    PlatformEventType.CAMPAIGN_RETRY_NEEDED: CustomerJourneyState.CAMPAIGN_RETRY,
    PlatformEventType.ESCALATION_CREATED: CustomerJourneyState.ESCALATED,
    PlatformEventType.ORCHESTRATION_STARTED: CustomerJourneyState.ORCHESTRATION_WAITING,
}

_EVENT_TITLE: dict[PlatformEventType, str] = {
    PlatformEventType.CALL_COMPLETED: "Voice call completed",
    PlatformEventType.WORKFLOW_COMPLETED: "Workflow completed",
    PlatformEventType.PAYMENT_INITIATED: "Payment initiated",
    PlatformEventType.PAYMENT_COMPLETED: "Payment received",
    PlatformEventType.PAYMENT_FAILED: "Payment failed",
    PlatformEventType.WHATSAPP_MESSAGE_SENT: "WhatsApp message sent",
    PlatformEventType.WHATSAPP_MESSAGE_FAILED: "WhatsApp message failed",
    PlatformEventType.EMAIL_SENT: "Email sent",
    PlatformEventType.EMAIL_FAILED: "Email failed",
    PlatformEventType.CAMPAIGN_RETRY_NEEDED: "Campaign retry scheduled",
    PlatformEventType.ESCALATION_CREATED: "Escalated to human agent",
    PlatformEventType.ORCHESTRATION_STARTED: "Durable workflow started",
    PlatformEventType.ORCHESTRATION_COMPLETED: "Durable workflow completed",
}


class CustomerTimelineIndexer:
    """Project platform events onto per-customer timeline entries."""

    async def index_platform_event(
        self,
        event: PlatformEvent,
        *,
        platform_event_db_id: int | None = None,
    ) -> int | None:
        if event.organization_id is None:
            return None

        payload = dict(event.payload or {})
        phone = payload.get("phone_e164")
        workflow_run_id = payload.get("workflow_run_id")
        transaction_id = payload.get("transaction_id")
        customer_id = payload.get("customer_id")

        ctx = await resolve_customer_context(
            event.organization_id,
            phone_e164=str(phone) if phone else None,
            workflow_run_id=int(workflow_run_id) if workflow_run_id else None,
            transaction_id=int(transaction_id) if transaction_id else None,
            customer_id=int(customer_id) if customer_id else None,
        )
        phone_e164 = ctx.get("phone_e164")
        if not phone_e164:
            return None

        channel = _EVENT_CHANNEL.get(event.event_type, TimelineChannel.SYSTEM)
        journey = _EVENT_JOURNEY.get(event.event_type)
        title = _EVENT_TITLE.get(event.event_type, event.event_type.value.replace(".", " ").title())
        summary = self._build_summary(event, payload)

        from api.db import db_client

        row = await db_client.upsert_customer_timeline_entry(
            organization_id=event.organization_id,
            phone_e164=phone_e164,
            customer_id=ctx.get("customer_id"),
            channel=channel.value,
            event_type=event.event_type.value,
            title=title,
            summary=summary,
            payload=payload,
            workflow_run_id=int(workflow_run_id) if workflow_run_id else None,
            conversation_id=int(payload["conversation_id"]) if payload.get("conversation_id") else None,
            transaction_id=int(transaction_id) if transaction_id else None,
            correlation_id=ctx.get("correlation_id") or event.correlation_id,
            journey_state=journey.value if journey else None,
            occurred_at=datetime.fromtimestamp(event.timestamp, tz=UTC),
            platform_event_id=platform_event_db_id,
            idempotency_key=event.idempotency_key or f"timeline:{event.event_id}",
        )
        if row:
            logger.debug(
                "indexed customer timeline entry id={} phone={} type={}",
                row.id,
                phone_e164,
                event.event_type.value,
            )
        return row.id if row else None

    @staticmethod
    def _build_summary(event: PlatformEvent, payload: dict[str, Any]) -> str | None:
        if event.event_type == PlatformEventType.PAYMENT_COMPLETED:
            receipt = payload.get("mpesa_receipt_number")
            return f"M-Pesa receipt {receipt}" if receipt else "Payment confirmed"
        if event.event_type == PlatformEventType.PAYMENT_FAILED:
            return str(payload.get("reason") or "Payment was not completed")
        if event.event_type == PlatformEventType.WHATSAPP_MESSAGE_SENT:
            template = payload.get("template_name")
            return f"Template: {template}" if template else payload.get("body", "")[:120] or None
        if event.event_type == PlatformEventType.EMAIL_SENT:
            subject = payload.get("subject")
            return str(subject) if subject else payload.get("body", "")[:120] or None
        if event.event_type == PlatformEventType.CAMPAIGN_RETRY_NEEDED:
            return f"Reason: {payload.get('reason', 'retry')}"
        if event.event_type in {
            PlatformEventType.CALL_COMPLETED,
            PlatformEventType.WORKFLOW_COMPLETED,
        }:
            run_id = payload.get("workflow_run_id")
            return f"Workflow run {run_id}" if run_id else None
        return None


TIMELINE_INDEXED_EVENT_TYPES = tuple(_EVENT_CHANNEL.keys())


_indexer: CustomerTimelineIndexer | None = None


def get_customer_timeline_indexer() -> CustomerTimelineIndexer:
    global _indexer
    if _indexer is None:
        _indexer = CustomerTimelineIndexer()
    return _indexer
