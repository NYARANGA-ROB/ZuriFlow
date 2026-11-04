"""Event-driven follow-ups that stay on the same customer conversation."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.services.omnichannel.orchestrator import get_channel_orchestrator
from api.services.omnichannel.types import (
    Channel,
    FollowupTrigger,
    MessagePurpose,
    OrchestrationAction,
)

DEFAULT_RULES: tuple[dict[str, Any], ...] = (
    {
        "trigger_event": FollowupTrigger.MISSED_CALL.value,
        "action": OrchestrationAction.SEND_SMS.value,
        "channel": Channel.SMS.value,
        "template_key": "missed_call_sms",
        "delay_seconds": 60,
        "purpose": MessagePurpose.TRANSACTIONAL.value,
    },
    {
        "trigger_event": FollowupTrigger.PAYMENT_SUCCESS.value,
        "action": OrchestrationAction.SEND_RECEIPT.value,
        "channel": Channel.SMS.value,
        "template_key": "mpesa_receipt",
        "delay_seconds": 0,
        "purpose": MessagePurpose.TRANSACTIONAL.value,
    },
    {
        "trigger_event": FollowupTrigger.APPOINTMENT_BOOKED.value,
        "action": OrchestrationAction.SEND_WHATSAPP.value,
        "channel": Channel.WHATSAPP.value,
        "template_key": "appointment_confirmation",
        "delay_seconds": 0,
        "purpose": MessagePurpose.TRANSACTIONAL.value,
    },
    {
        "trigger_event": FollowupTrigger.APPOINTMENT_TOMORROW.value,
        "action": OrchestrationAction.SEND_SMS.value,
        "channel": Channel.SMS.value,
        "template_key": "appointment_reminder",
        "delay_seconds": 0,
        "purpose": MessagePurpose.TRANSACTIONAL.value,
    },
    {
        "trigger_event": FollowupTrigger.HUMAN_REQUESTED.value,
        "action": OrchestrationAction.ESCALATE.value,
        "channel": Channel.VOICE.value,
        "template_key": "human_handoff",
        "delay_seconds": 0,
        "purpose": MessagePurpose.TRANSACTIONAL.value,
    },
)

_BODIES = {
    "missed_call_sms": "We missed your call. Reply to this SMS or WhatsApp us and we will help.",
    "mpesa_receipt": "Payment received. This is your M-Pesa receipt confirmation.",
    "appointment_confirmation": "Your appointment is booked. We will remind you tomorrow.",
    "appointment_reminder": "Reminder: you have an appointment tomorrow.",
    "human_handoff": "A teammate has been notified to continue this conversation.",
}


class FollowupEngine:
    async def ensure_defaults(self, organization_id: int) -> list[Any]:
        existing = await db_client.list_followup_rules(
            organization_id=organization_id, enabled_only=False
        )
        if existing:
            return existing
        created = []
        for rule in DEFAULT_RULES:
            created.append(
                await db_client.create_followup_rule(organization_id=organization_id, **rule)
            )
        return created

    async def handle(
        self,
        *,
        organization_id: int,
        trigger: FollowupTrigger | str,
        phone: str | None = None,
        customer_id: int | None = None,
        body: str | None = None,
        transaction_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        trigger = FollowupTrigger(trigger)
        await self.ensure_defaults(organization_id)
        rules = await db_client.list_followup_rules(
            organization_id=organization_id,
            trigger_event=trigger.value,
        )
        orchestrator = get_channel_orchestrator()
        results = []
        for rule in rules:
            results.append(
                await orchestrator.execute(
                    organization_id=organization_id,
                    action=rule.action,
                    phone=phone,
                    customer_id=customer_id,
                    body=body or _BODIES.get(rule.template_key or "", None),
                    purpose=rule.purpose,
                    channel=rule.channel,
                    transaction_id=transaction_id,
                    metadata={"trigger": trigger.value, "rule_id": rule.id, **(metadata or {})},
                )
            )
        return results


_engine: FollowupEngine | None = None


def get_followup_engine() -> FollowupEngine:
    global _engine
    if _engine is None:
        _engine = FollowupEngine()
    return _engine
