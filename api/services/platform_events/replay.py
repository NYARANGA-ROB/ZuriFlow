"""Tenant-scoped platform event replay."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from api.db import db_client
from api.services.platform_events.router import get_platform_event_router
from api.services.platform_events.schema import PlatformEvent


class PlatformEventReplay:
    """Re-dispatch persisted events for recovery or backfill."""

    async def replay_organization(
        self,
        organization_id: int,
        *,
        event_type: str | None = None,
        since_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        rows = await db_client.list_platform_events(
            organization_id=organization_id,
            event_type=event_type,
            since_id=since_id,
            from_ts=from_ts,
            to_ts=to_ts,
            limit=limit,
        )
        return await self._replay_rows(rows)

    async def replay_correlation(
        self,
        correlation_id: str,
        *,
        organization_id: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        rows = await db_client.list_platform_events(
            organization_id=organization_id,
            correlation_id=correlation_id,
            limit=limit,
        )
        return await self._replay_rows(rows)

    async def replay_event(self, event_id: str) -> dict[str, Any]:
        row = await db_client.get_platform_event(event_id)
        if row is None:
            return {"replayed": 0, "failed": 0, "total": 0, "reason": "not_found"}
        return await self._replay_rows([row])

    async def _replay_rows(self, rows: list[Any]) -> dict[str, Any]:
        router = get_platform_event_router()
        replayed = 0
        failed = 0
        for row in rows:
            event = PlatformEvent.from_db_row(row)
            try:
                result = await router.dispatch(event)
                if result.get("failed", 0) > 0:
                    failed += 1
                else:
                    replayed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "platform event replay failed event_id={}: {}",
                    event.event_id,
                    exc,
                )
        return {
            "replayed": replayed,
            "failed": failed,
            "total": len(rows),
        }


_replay: PlatformEventReplay | None = None


def get_platform_event_replay() -> PlatformEventReplay:
    global _replay
    if _replay is None:
        _replay = PlatformEventReplay()
    return _replay
