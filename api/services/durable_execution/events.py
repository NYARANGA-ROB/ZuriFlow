"""Append-only orchestration event log."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.services.durable_execution.persistence import (
    OrchestrationPersistence,
    get_orchestration_persistence,
)
from api.services.durable_execution.types import OrchestrationEventType


class OrchestrationEventEngine:
    """Idempotent event append and replay helpers."""

    def __init__(self, persistence: OrchestrationPersistence | None = None) -> None:
        self._persistence = persistence or get_orchestration_persistence()

    async def emit(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        event_type: OrchestrationEventType,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> bool:
        """Append event. Returns False if idempotency_key already exists."""
        row = await self._persistence.append_event(
            orchestration_id=orchestration_id,
            organization_id=organization_id,
            event_type=event_type,
            payload=payload or {},
            idempotency_key=idempotency_key,
        )
        if row is None:
            logger.debug(
                "durable orchestration event deduplicated key={} orch={}",
                idempotency_key,
                orchestration_id,
            )
            return False
        return True

    async def replay_from(
        self,
        orchestration_id: int,
        *,
        since_event_id: int | None = None,
    ) -> list[dict[str, Any]]:
        events = await self._persistence.list_events(orchestration_id, limit=500)
        replay: list[dict[str, Any]] = []
        for event in events:
            if since_event_id is not None and event.id <= since_event_id:
                continue
            replay.append(
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "payload": dict(event.payload or {}),
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
            )
        return replay


_event_engine: OrchestrationEventEngine | None = None


def get_orchestration_event_engine() -> OrchestrationEventEngine:
    global _event_engine
    if _event_engine is None:
        _event_engine = OrchestrationEventEngine()
    return _event_engine
