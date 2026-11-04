"""Tests for platform event bus."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.platform_events.router import PlatformEventRouter
from api.services.platform_events.schema import (
    PlatformEvent,
    PlatformEventSource,
    PlatformEventType,
)


@pytest.mark.asyncio
async def test_router_dispatches_registered_handler():
    router = PlatformEventRouter()
    seen: list[str] = []

    async def handler(event: PlatformEvent) -> None:
        seen.append(event.event_id)

    router.register(PlatformEventType.CALL_COMPLETED, handler, name="test_handler")
    event = PlatformEvent(
        event_type=PlatformEventType.CALL_COMPLETED,
        organization_id=1,
        source=PlatformEventSource.SYSTEM,
        payload={"workflow_run_id": 99},
    )
    with patch(
        "api.services.platform_events.router.get_platform_event_observability"
    ) as obs_mock:
        obs_mock.return_value.record_handled = AsyncMock()
        obs_mock.return_value.record_failed = AsyncMock()
        result = await router.dispatch(event)
    assert result["handled"] == 1
    assert seen == [event.event_id]


@pytest.mark.asyncio
async def test_router_schedules_retry_on_handler_failure():
    router = PlatformEventRouter()
    dlq = AsyncMock()
    dlq.schedule_retry = AsyncMock()

    async def flaky(_event: PlatformEvent) -> None:
        raise RuntimeError("boom")

    router.register(PlatformEventType.PAYMENT_FAILED, flaky, name="flaky")
    event = PlatformEvent(
        event_type=PlatformEventType.PAYMENT_FAILED,
        organization_id=5,
        source=PlatformEventSource.MPESA,
        payload={"transaction_id": 1},
    )

    with patch(
        "api.services.platform_events.router.get_platform_event_dlq",
        return_value=dlq,
    ), patch(
        "api.services.platform_events.router.get_platform_event_observability"
    ) as obs_mock:
        obs_mock.return_value.record_handled = AsyncMock()
        obs_mock.return_value.record_failed = AsyncMock()
        result = await router.dispatch(event)

    assert result["failed"] == 1
    dlq.schedule_retry.assert_awaited_once()


@pytest.mark.asyncio
async def test_bus_publish_deduplicates_by_idempotency_key():
    from api.services.platform_events.bus import PlatformEventBus

    bus = PlatformEventBus(redis_client=AsyncMock())
    bus._enqueue_route = AsyncMock()

    existing = MagicMock()
    existing.event_id = "evt-existing"
    existing.id = 42

    with patch("api.services.platform_events.bus.db_client") as mock_db, patch(
        "api.services.platform_events.observability.get_platform_event_observability"
    ) as obs_mock:
        mock_db.insert_platform_event = AsyncMock(return_value=None)
        mock_db.get_platform_event_by_idempotency_key = AsyncMock(return_value=existing)
        obs_mock.return_value.record_published = AsyncMock()

        event = PlatformEvent(
            event_type=PlatformEventType.WORKFLOW_COMPLETED,
            organization_id=1,
            source=PlatformEventSource.WORKFLOW_COMPLETION,
            idempotency_key="workflow.completed:7",
            payload={"workflow_run_id": 7},
        )
        with patch("api.services.platform_events.bus.PLATFORM_EVENTS_ENABLED", True):
            result = await bus.publish(event)

    assert result["deduplicated"] is True
    assert result["event_id"] == "evt-existing"
    bus._enqueue_route.assert_not_called()


@pytest.mark.asyncio
async def test_campaign_event_mapping():
    from api.services.platform_events.adapters import publish_campaign_event_from_json
    import json

    bus = AsyncMock()
    bus.enabled = True
    bus.publish = AsyncMock(return_value={"published": True})
    with patch(
        "api.services.platform_events.adapters.get_platform_event_bus",
        return_value=bus,
    ):
        raw = json.dumps(
            {
                "type": "retry_needed",
                "campaign_id": 12,
                "workflow_run_id": 3,
                "reason": "busy",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        result = await publish_campaign_event_from_json(raw, organization_id=9)
    assert result is not None
    bus.publish.assert_awaited_once()
    published = bus.publish.await_args.args[0]
    assert published.event_type == PlatformEventType.CAMPAIGN_RETRY_NEEDED
