"""Replay failed or missed events from the durable log."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from api.services.call_reliability.dead_letter import DeadLetterQueue, get_dead_letter_queue
from api.services.call_reliability.event_store import DurableEventStore, get_durable_event_store
from api.services.call_reliability.types import ReliabilityEvent, ReliabilityEventType


class EventReplaySystem:
    """Re-process stored events idempotently after failures."""

    def __init__(
        self,
        store: DurableEventStore | None = None,
        dlq: DeadLetterQueue | None = None,
    ) -> None:
        self._store = store or get_durable_event_store()
        self._dlq = dlq or get_dead_letter_queue()

    async def replay_session(
        self,
        session_id: str,
        *,
        since_event_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        events = await self._store.list_session_events(session_id, limit=limit)
        return await self._replay_events(events, since_event_id=since_event_id)

    async def replay_workflow(
        self,
        workflow_run_id: int,
        *,
        since_event_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        events = await self._store.list_workflow_events(workflow_run_id, limit=limit)
        return await self._replay_events(events, since_event_id=since_event_id)

    async def _replay_events(
        self,
        events: list[ReliabilityEvent],
        *,
        since_event_id: str | None = None,
    ) -> dict[str, Any]:
        replaying = since_event_id is None
        replayed = 0
        failed = 0
        skipped = 0

        for event in events:
            if not replaying:
                if event.event_id == since_event_id:
                    replaying = True
                continue
            if not replaying:
                skipped += 1
                continue
            ok = await self._dispatch(event)
            if ok:
                replayed += 1
            else:
                failed += 1

        return {
            "replayed": replayed,
            "failed": failed,
            "skipped": skipped,
            "total": len(events),
        }

    async def _dispatch(self, event: ReliabilityEvent) -> bool:
        try:
            if event.event_type == ReliabilityEventType.WORKFLOW_INTERRUPTED:
                return await self._recover_workflow(event)
            if event.event_type == ReliabilityEventType.CALL_FAILED:
                return await self._schedule_call_retry(event)
            if event.event_type == ReliabilityEventType.TRANSCRIPT:
                return await self._replay_transcript(event)
            if event.event_type == ReliabilityEventType.PAYMENT:
                return await self._replay_payment(event)
            return True
        except Exception as exc:
            logger.warning(
                "event replay failed event_id={} type={}: {}",
                event.event_id,
                event.event_type.value,
                exc,
            )
            await self._dlq.enqueue_event(event, error=str(exc))
            return False

    async def _recover_workflow(self, event: ReliabilityEvent) -> bool:
        if not event.workflow_run_id:
            return False
        from api.db import db_client

        run = await db_client.get_workflow_run_by_id(event.workflow_run_id)
        if not run:
            return False
        gathered = dict(run.gathered_context or {})
        checkpoint = event.payload.get("checkpoint") or event.payload
        gathered["reliability_recovery"] = {
            "recovered_at": time.time(),
            "checkpoint": checkpoint,
        }
        await db_client.update_workflow_run(
            run_id=event.workflow_run_id,
            gathered_context=gathered,
        )
        return True

    async def _schedule_call_retry(self, event: ReliabilityEvent) -> bool:
        from api.services.call_reliability.retry_queues import get_call_retry_queue
        from api.services.call_reliability.types import RecoveryKind

        job = await get_call_retry_queue().schedule(
            organization_id=event.organization_id,
            kind=RecoveryKind.CALL_RETRY,
            reason=event.payload.get("reason", "replay"),
            workflow_run_id=event.workflow_run_id,
            session_id=event.session_id,
            payload=event.payload,
        )
        return job is not None

    async def _replay_transcript(self, event: ReliabilityEvent) -> bool:
        session_id = event.session_id
        text = str(event.payload.get("text", ""))
        if not session_id or not text:
            return False
        try:
            from api.services.debt_collection.engine import get_debt_collection_engine

            engine = get_debt_collection_engine()
            if engine.get_session(session_id) is None:
                return False
            await engine.handle_transcript(session_id, text)
            return True
        except Exception:
            return False

    async def _replay_payment(self, event: ReliabilityEvent) -> bool:
        session_id = event.session_id
        if not session_id:
            return False
        try:
            from api.services.debt_collection.engine import get_debt_collection_engine

            engine = get_debt_collection_engine()
            if engine.get_session(session_id) is None:
                return False
            await engine.record_payment(
                session_id,
                status=str(event.payload.get("status", "success")),
                amount=event.payload.get("amount"),
                receipt=str(event.payload.get("receipt", "")),
            )
            return True
        except Exception:
            return False


_replay: EventReplaySystem | None = None


def get_event_replay_system() -> EventReplaySystem:
    global _replay
    if _replay is None:
        _replay = EventReplaySystem()
    return _replay
