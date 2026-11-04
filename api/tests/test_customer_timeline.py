"""Tests for omnichannel customer timeline."""

from __future__ import annotations

import pytest

from api.services.customer_timeline.correlation import customer_correlation_id
from api.services.customer_timeline.state_machine import (
    active_channels,
    derive_journey_state,
)
from api.services.customer_timeline.types import CustomerJourneyState
from api.services.platform_events.schema import PlatformEventType


def test_customer_correlation_id():
    corr = customer_correlation_id("+254712345678")
    assert corr.startswith("customer:")
    assert "254712345678" in corr


def test_derive_journey_state_payment_completed():
    entries = [
        {
            "event_type": PlatformEventType.PAYMENT_COMPLETED.value,
            "channel": "payment",
            "occurred_at": "2026-06-24T12:00:00+00:00",
        }
    ]
    assert derive_journey_state(entries) == CustomerJourneyState.PAYMENT_COMPLETED


def test_derive_journey_state_whatsapp_after_voice():
    entries = [
        {
            "event_type": PlatformEventType.WHATSAPP_MESSAGE_SENT.value,
            "channel": "whatsapp",
            "occurred_at": "2026-06-24T13:00:00+00:00",
        },
        {
            "event_type": PlatformEventType.CALL_COMPLETED.value,
            "channel": "voice",
            "occurred_at": "2026-06-24T12:00:00+00:00",
        },
    ]
    assert derive_journey_state(entries) == CustomerJourneyState.WHATSAPP_FOLLOW_UP


def test_active_channels():
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    entries = [
        {"channel": "voice", "occurred_at": (now - timedelta(hours=1)).isoformat()},
        {"channel": "whatsapp", "occurred_at": now.isoformat()},
    ]
    channels = active_channels(entries, window_hours=72)
    assert "voice" in channels
    assert "whatsapp" in channels


def test_derive_journey_state_email():
    entries = [
        {
            "event_type": PlatformEventType.EMAIL_SENT.value,
            "channel": "email",
            "occurred_at": "2026-06-24T14:00:00+00:00",
        }
    ]
    assert derive_journey_state(entries) == CustomerJourneyState.EMAIL_FOLLOW_UP


@pytest.mark.asyncio
async def test_indexer_maps_event_to_timeline_entry():
    from unittest.mock import AsyncMock, MagicMock, patch

    from api.services.customer_timeline.indexer import CustomerTimelineIndexer
    from api.services.platform_events.schema import PlatformEvent, PlatformEventSource

    indexer = CustomerTimelineIndexer()
    event = PlatformEvent(
        event_type=PlatformEventType.CALL_COMPLETED,
        organization_id=1,
        source=PlatformEventSource.WORKFLOW_COMPLETION,
        payload={"workflow_run_id": 42, "phone_e164": "+254700000001"},
        idempotency_key="call.completed:42",
    )

    mock_row = MagicMock()
    mock_row.id = 99

    with patch(
        "api.services.customer_timeline.indexer.resolve_customer_context",
        AsyncMock(
            return_value={
                "phone_e164": "+254700000001",
                "customer_id": 5,
                "correlation_id": "customer:+254700000001",
            }
        ),
    ), patch("api.db.db_client") as mock_db:
        mock_db.upsert_customer_timeline_entry = AsyncMock(return_value=mock_row)
        entry_id = await indexer.index_platform_event(event, platform_event_db_id=7)

    assert entry_id == 99
    mock_db.upsert_customer_timeline_entry.assert_awaited_once()
    call_kwargs = mock_db.upsert_customer_timeline_entry.await_args.kwargs
    assert call_kwargs["channel"] == "voice"
    assert call_kwargs["phone_e164"] == "+254700000001"
