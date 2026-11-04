"""Bridge durable orchestration lifecycle events to the platform event bus."""

from __future__ import annotations

from typing import Any

from api.constants import PLATFORM_EVENTS_ENABLED
from api.services.platform_events.adapters import publish_orchestration_event
from api.services.platform_events.schema import PlatformEventType


async def publish_durable_lifecycle_event(
    *,
    organization_id: int,
    orchestration_id: int,
    definition_name: str,
    orchestration_key: str,
    event_type: PlatformEventType,
    workflow_run_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    if not PLATFORM_EVENTS_ENABLED:
        return
    await publish_orchestration_event(
        organization_id=organization_id,
        orchestration_id=orchestration_id,
        definition_name=definition_name,
        orchestration_key=orchestration_key,
        event_type=event_type,
        workflow_run_id=workflow_run_id,
        extra=extra,
    )
