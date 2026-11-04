"""Recovery workers for failed calls and interrupted workflows."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from api.services.call_reliability.dead_letter import get_dead_letter_queue
from api.services.call_reliability.event_replay import get_event_replay_system
from api.services.call_reliability.event_store import get_durable_event_store
from api.services.call_reliability.failure_monitor import get_failure_monitor
from api.services.call_reliability.retry_queues import get_call_retry_queue
from api.services.call_reliability.types import (
    FailureSeverity,
    RecoveryKind,
    ReliabilityEventType,
    RetryJob,
)


class RecoveryWorkerService:
    """Process retry queue jobs and restore interrupted operations."""

    async def process_organization(self, organization_id: int) -> dict[str, Any]:
        queue = get_call_retry_queue()
        jobs = await queue.claim_due(organization_id)
        results = {
            "organization_id": organization_id,
            "claimed": len(jobs),
            "succeeded": 0,
            "failed": 0,
            "dead_lettered": 0,
        }
        for job in jobs:
            ok = await self._process_job(job)
            if ok:
                results["succeeded"] += 1
            else:
                results["failed"] += 1
                if job.attempt >= job.max_attempts:
                    await get_dead_letter_queue().enqueue_job(
                        job, error="max_retries_exceeded"
                    )
                    results["dead_lettered"] += 1
                else:
                    await queue.schedule(
                        organization_id=job.organization_id,
                        kind=job.kind,
                        reason=job.reason,
                        workflow_run_id=job.workflow_run_id,
                        session_id=job.session_id,
                        attempt=job.attempt + 1,
                        payload=job.payload,
                    )
        return results

    async def _process_job(self, job: RetryJob) -> bool:
        try:
            if job.kind == RecoveryKind.CALL_RETRY:
                return await self._retry_call(job)
            if job.kind == RecoveryKind.WORKFLOW_RESUME:
                return await self._resume_workflow(job)
            if job.kind == RecoveryKind.EVENT_REPLAY:
                return await self._replay_events(job)
            if job.kind == RecoveryKind.WEBSOCKET_CHECKPOINT:
                return await self._restore_websocket(job)
            return False
        except Exception as exc:
            logger.exception(
                "recovery job failed job_id={} kind={}: {}",
                job.job_id,
                job.kind.value,
                exc,
            )
            await get_failure_monitor().record(
                organization_id=job.organization_id,
                category="recovery_worker",
                message=str(exc),
                severity=FailureSeverity.HIGH,
                session_id=job.session_id,
                workflow_run_id=job.workflow_run_id,
                metadata={"job_id": job.job_id, "kind": job.kind.value},
            )
            return False

    async def _retry_call(self, job: RetryJob) -> bool:
        campaign_id = job.payload.get("campaign_id")
        queued_run_id = job.payload.get("queued_run_id")
        if campaign_id and queued_run_id:
            try:
                from api.services.campaign.campaign_call_dispatcher import (
                    CampaignCallDispatcher,
                )
                from api.db import db_client

                campaign = await db_client.get_campaign_by_id(int(campaign_id))
                queued_run = await db_client.get_queued_run_by_id(int(queued_run_id))
                if campaign and queued_run:
                    dispatcher = CampaignCallDispatcher()
                    await dispatcher.dispatch_call(queued_run, campaign, slot_id="recovery")
                    return True
            except Exception:
                pass

        if job.workflow_run_id:
            await get_durable_event_store().append_simple(
                ReliabilityEventType.CALL_RETRY_SCHEDULED,
                organization_id=job.organization_id,
                workflow_run_id=job.workflow_run_id,
                session_id=job.session_id,
                payload={"attempt": job.attempt, "reason": job.reason},
            )
            return True
        return False

    async def _resume_workflow(self, job: RetryJob) -> bool:
        if not job.workflow_run_id:
            return False
        replay = get_event_replay_system()
        result = await replay.replay_workflow(job.workflow_run_id)
        await get_durable_event_store().append_simple(
            ReliabilityEventType.WORKFLOW_RECOVERED,
            organization_id=job.organization_id,
            workflow_run_id=job.workflow_run_id,
            session_id=job.session_id,
            payload=result,
        )
        return result.get("failed", 0) == 0

    async def _replay_events(self, job: RetryJob) -> bool:
        replay = get_event_replay_system()
        if job.session_id:
            result = await replay.replay_session(job.session_id)
        elif job.workflow_run_id:
            result = await replay.replay_workflow(job.workflow_run_id)
        else:
            return False
        return result.get("failed", 0) == 0

    async def _restore_websocket(self, job: RetryJob) -> bool:
        from api.services.call_reliability.websocket_recovery import (
            get_websocket_session_recovery,
        )

        if not job.session_id:
            return False
        state = await get_websocket_session_recovery().load_checkpoint(job.session_id)
        return state is not None

    async def record_call_failure(
        self,
        *,
        organization_id: int,
        reason: str,
        workflow_run_id: int = 0,
        session_id: str = "",
        severity: FailureSeverity = FailureSeverity.MEDIUM,
        payload: dict[str, Any] | None = None,
        schedule_retry: bool = True,
    ) -> dict[str, Any]:
        store = get_durable_event_store()
        await store.append_simple(
            ReliabilityEventType.CALL_FAILED,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            session_id=session_id,
            payload={"reason": reason, **(payload or {})},
            idempotency_key=f"call_failed:{workflow_run_id}:{session_id}:{reason}",
        )
        await get_failure_monitor().record(
            organization_id=organization_id,
            category="call_failed",
            message=reason,
            severity=severity,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            metadata=payload,
        )
        job = None
        if schedule_retry:
            job = await get_call_retry_queue().schedule(
                organization_id=organization_id,
                kind=RecoveryKind.CALL_RETRY,
                reason=reason,
                workflow_run_id=workflow_run_id,
                session_id=session_id,
                payload=dict(payload or {}),
            )
        return {
            "recorded": True,
            "retry_scheduled": job is not None,
            "job_id": getattr(job, "job_id", None) if job else None,
        }

    async def record_workflow_interrupted(
        self,
        *,
        organization_id: int,
        workflow_run_id: int,
        session_id: str = "",
        checkpoint: dict[str, Any] | None = None,
    ) -> None:
        store = get_durable_event_store()
        await store.append_simple(
            ReliabilityEventType.WORKFLOW_INTERRUPTED,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            session_id=session_id,
            payload={"checkpoint": checkpoint or {}, "interrupted_at": time.time()},
        )
        await get_call_retry_queue().schedule(
            organization_id=organization_id,
            kind=RecoveryKind.WORKFLOW_RESUME,
            reason="workflow_interrupted",
            workflow_run_id=workflow_run_id,
            session_id=session_id,
            payload={"checkpoint": checkpoint or {}},
        )
        await get_failure_monitor().record(
            organization_id=organization_id,
            category="workflow_interrupted",
            message="workflow_interrupted",
            severity=FailureSeverity.HIGH,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
        )


_worker: RecoveryWorkerService | None = None


def get_recovery_worker_service() -> RecoveryWorkerService:
    global _worker
    if _worker is None:
        _worker = RecoveryWorkerService()
    return _worker
