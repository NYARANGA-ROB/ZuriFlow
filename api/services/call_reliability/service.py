"""Facade for call reliability and recovery."""

from __future__ import annotations

from typing import Any

from api.constants import CALL_RELIABILITY_ENABLED
from api.services.call_reliability.config import DEFAULT_CALL_RELIABILITY_CONFIG
from api.services.call_reliability.dead_letter import get_dead_letter_queue
from api.services.call_reliability.event_replay import get_event_replay_system
from api.services.call_reliability.event_store import get_durable_event_store
from api.services.call_reliability.failure_monitor import get_failure_monitor
from api.services.call_reliability.recovery_workers import get_recovery_worker_service
from api.services.call_reliability.retry_queues import get_call_retry_queue
from api.services.call_reliability.types import FailureSeverity, ReliabilityEventType
from api.services.call_reliability.websocket_recovery import get_websocket_session_recovery


class CallReliabilityService:
    """Production reliability orchestration for AI voice call operations."""

    def __init__(self) -> None:
        self._workers = get_recovery_worker_service()
        self._store = get_durable_event_store()
        self._replay = get_event_replay_system()
        self._retry = get_call_retry_queue()
        self._dlq = get_dead_letter_queue()
        self._monitor = get_failure_monitor()
        self._ws = get_websocket_session_recovery()

    @property
    def enabled(self) -> bool:
        return CALL_RELIABILITY_ENABLED

    async def record_event(self, event_type: ReliabilityEventType, **kwargs):
        return await self._store.append_simple(event_type, **kwargs)

    async def record_call_failure(self, **kwargs) -> dict[str, Any]:
        if not self.enabled:
            return {"recorded": False}
        return await self._workers.record_call_failure(**kwargs)

    async def record_workflow_interrupted(self, **kwargs) -> None:
        if not self.enabled:
            return
        await self._workers.record_workflow_interrupted(**kwargs)

    async def process_retries(self, organization_id: int) -> dict[str, Any]:
        return await self._workers.process_organization(organization_id)

    async def replay_session(self, session_id: str, **kwargs) -> dict[str, Any]:
        return await self._replay.replay_session(session_id, **kwargs)

    async def replay_workflow(self, workflow_run_id: int, **kwargs) -> dict[str, Any]:
        return await self._replay.replay_workflow(workflow_run_id, **kwargs)

    async def failure_summary(self, organization_id: int, *, days: int = 7):
        return await self._monitor.summary(organization_id, days=days)

    async def list_dlq(self, organization_id: int, *, limit: int = 50):
        return await self._dlq.list_entries(organization_id, limit=limit)

    async def list_pending_retries(self, organization_id: int, *, limit: int = 50):
        return await self._retry.list_pending(organization_id, limit=limit)

    async def save_ws_checkpoint(self, **kwargs) -> None:
        if self.enabled:
            await self._ws.save_checkpoint(**kwargs)

    async def restore_ws_checkpoint(self, session_id: str):
        return await self._ws.load_checkpoint(session_id)

    def status(self) -> dict[str, Any]:
        cfg = DEFAULT_CALL_RELIABILITY_CONFIG
        return {
            "enabled": self.enabled,
            "max_retries": cfg.max_retries,
            "retry_base_delay_s": cfg.retry_base_delay_s,
            "event_ttl_s": cfg.event_ttl_s,
            "dlq_ttl_s": cfg.dlq_ttl_s,
            "ws_checkpoint_ttl_s": cfg.ws_checkpoint_ttl_s,
            "features": [
                "retry_queues",
                "recovery_workers",
                "dead_letter_queues",
                "event_replay",
                "failure_monitoring",
                "websocket_checkpoints",
            ],
        }


_service: CallReliabilityService | None = None


def get_call_reliability_service() -> CallReliabilityService:
    global _service
    if _service is None:
        _service = CallReliabilityService()
    return _service
