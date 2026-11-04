"""Per-session voice pipeline registry — survives WebSocket reconnect within grace."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from loguru import logger

from api.services.realtime_voice_pipeline.orchestrator import RealtimeVoiceOrchestrator

PipelineFactory = Callable[..., RealtimeVoiceOrchestrator]


@dataclass
class VoicePipelineSessionRegistry:
    """One orchestrator per ``session_id``; detached on WS drop, stopped on session expiry."""

    _orchestrators: dict[str, RealtimeVoiceOrchestrator] = field(default_factory=dict)
    _tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def ensure_running(
        self,
        session_id: str,
        factory: Callable[[], RealtimeVoiceOrchestrator],
        *,
        resumed: bool,
    ) -> RealtimeVoiceOrchestrator:
        stop_orch: RealtimeVoiceOrchestrator | None = None
        cancel_task: asyncio.Task | None = None

        async with self._lock:
            existing = self._orchestrators.get(session_id)
            task = self._tasks.get(session_id)
            if existing is not None and task is not None and not task.done():
                if resumed:
                    logger.debug(
                        "voice pipeline already active session_id={} (reconnect)",
                        session_id[:8],
                    )
                return existing

            if existing is not None:
                stop_orch = self._orchestrators.pop(session_id, None)
            if task is not None:
                if not task.done():
                    cancel_task = task
                self._tasks.pop(session_id, None)

        if stop_orch is not None:
            await stop_orch.stop()
        if cancel_task is not None:
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)

        async with self._lock:
            orch = factory()
            self._orchestrators[session_id] = orch
            self._tasks[session_id] = asyncio.create_task(
                self._run_pipeline(session_id, orch),
                name=f"voice-pipeline-{session_id[:8]}",
            )
            return orch

    async def _run_pipeline(self, session_id: str, orch: RealtimeVoiceOrchestrator) -> None:
        try:
            await orch.run()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(
                "voice pipeline crashed session_id={}: {}",
                session_id[:8],
                e,
            )
            await self._record_pipeline_failure(session_id, str(e))
        finally:
            async with self._lock:
                if self._orchestrators.get(session_id) is orch:
                    self._orchestrators.pop(session_id, None)
                    self._tasks.pop(session_id, None)

    async def stop(self, session_id: str) -> None:
        async with self._lock:
            orch = self._orchestrators.pop(session_id, None)
            task = self._tasks.pop(session_id, None)
        if orch is not None:
            await orch.stop()
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def has_active(self, session_id: str) -> bool:
        task = self._tasks.get(session_id)
        return task is not None and not task.done()

    async def _record_pipeline_failure(self, session_id: str, error: str) -> None:
        try:
            from api.constants import CALL_RELIABILITY_ENABLED

            if not CALL_RELIABILITY_ENABLED:
                return
            orch = self._orchestrators.get(session_id)
            organization_id = 0
            workflow_run_id = 0
            if orch is not None:
                cfg = getattr(orch, "deps", None)
                if cfg is not None:
                    organization_id = int(getattr(cfg.config, "organization_id", 0) or 0)
                    workflow_run_id = int(getattr(cfg, "workflow_run_id", 0) or 0)
            from api.services.call_reliability.service import get_call_reliability_service

            svc = get_call_reliability_service()
            await svc.record_call_failure(
                organization_id=organization_id,
                reason="voice_pipeline_crash",
                workflow_run_id=workflow_run_id,
                session_id=session_id,
                payload={"error": error},
            )
            if workflow_run_id:
                await svc.record_workflow_interrupted(
                    organization_id=organization_id,
                    workflow_run_id=workflow_run_id,
                    session_id=session_id,
                    checkpoint={"error": error},
                )
        except Exception:
            pass


_registry: VoicePipelineSessionRegistry | None = None


def get_voice_pipeline_registry() -> VoicePipelineSessionRegistry:
    global _registry
    if _registry is None:
        _registry = VoicePipelineSessionRegistry()
    return _registry
