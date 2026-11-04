"""Derive cross-channel customer journey state from timeline entries."""

from __future__ import annotations

from api.services.customer_timeline.types import CustomerJourneyState, TimelineChannel
from api.services.platform_events.schema import PlatformEventType


def derive_journey_state(
    entries: list[dict],
    *,
    default: CustomerJourneyState = CustomerJourneyState.IDLE,
) -> CustomerJourneyState:
    """Walk recent entries (newest first) to infer current journey phase."""
    if not entries:
        return default

    for entry in entries:
        event_type = str(entry.get("event_type") or "")
        channel = str(entry.get("channel") or "")
        journey = entry.get("journey_state")
        if journey:
            try:
                return CustomerJourneyState(journey)
            except ValueError:
                pass

        if event_type == PlatformEventType.ESCALATION_CREATED.value:
            return CustomerJourneyState.ESCALATED
        if event_type in {
            PlatformEventType.PAYMENT_COMPLETED.value,
        }:
            return CustomerJourneyState.PAYMENT_COMPLETED
        if event_type in {
            PlatformEventType.PAYMENT_FAILED.value,
            PlatformEventType.PAYMENT_TIMEOUT.value,
        }:
            return CustomerJourneyState.PAYMENT_FAILED
        if event_type in {
            PlatformEventType.PAYMENT_INITIATED.value,
        }:
            return CustomerJourneyState.PAYMENT_PENDING
        if event_type in {
            PlatformEventType.WHATSAPP_MESSAGE_SENT.value,
            PlatformEventType.WHATSAPP_MESSAGE_FAILED.value,
        }:
            return CustomerJourneyState.WHATSAPP_FOLLOW_UP
        if event_type in {
            PlatformEventType.EMAIL_SENT.value,
            PlatformEventType.EMAIL_FAILED.value,
        }:
            return CustomerJourneyState.EMAIL_FOLLOW_UP
        if event_type == PlatformEventType.CAMPAIGN_RETRY_NEEDED.value:
            return CustomerJourneyState.CAMPAIGN_RETRY
        if event_type in {
            PlatformEventType.ORCHESTRATION_STARTED.value,
            PlatformEventType.ORCHESTRATION_SIGNAL.value,
        }:
            return CustomerJourneyState.ORCHESTRATION_WAITING
        if event_type == PlatformEventType.CALL_COMPLETED.value:
            return CustomerJourneyState.VOICE_COMPLETED
        if event_type == PlatformEventType.CALL_FAILED.value:
            return CustomerJourneyState.VOICE_COMPLETED
        if channel == TimelineChannel.VOICE.value:
            return CustomerJourneyState.VOICE_ACTIVE

    return default


def active_channels(entries: list[dict], *, window_hours: int = 72) -> list[str]:
    """Channels touched in the recent timeline window."""
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    channels: set[str] = set()
    for entry in entries:
        occurred = entry.get("occurred_at")
        if occurred:
            try:
                ts = datetime.fromisoformat(str(occurred).replace("Z", "+00:00"))
                if ts < cutoff:
                    continue
            except ValueError:
                pass
        channel = entry.get("channel")
        if channel:
            channels.add(str(channel))
    return sorted(channels)
