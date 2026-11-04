"""Tests for call reliability and recovery."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from api.services.call_reliability.retry_queues import CallRetryQueue
from api.services.call_reliability.types import RecoveryKind, ReliabilityEvent, ReliabilityEventType


def test_reliability_event_roundtrip():
    event = ReliabilityEvent(
        event_id="e1",
        event_type=ReliabilityEventType.CALL_FAILED,
        organization_id=1,
        session_id="sess-1",
        workflow_run_id=42,
        timestamp=time.time(),
        payload={"reason": "test"},
    )
    restored = ReliabilityEvent.from_dict(event.to_dict())
    assert restored.event_type == ReliabilityEventType.CALL_FAILED
    assert restored.workflow_run_id == 42


@pytest.mark.asyncio
async def test_retry_queue_schedule_and_claim():
    fake = AsyncMock()
    fake.pipeline = lambda: fake
    fake.zadd = AsyncMock()
    fake.setex = AsyncMock()
    fake.expire = AsyncMock()
    fake.execute = AsyncMock()
    fake.zrangebyscore = AsyncMock(return_value=[])
    fake.zrem = AsyncMock()

    queue = CallRetryQueue(redis_client=fake, config=type("C", (), {
        "max_retries": 3,
        "retry_base_delay_s": 1.0,
        "event_ttl_s": 60,
    })())

    job = await queue.schedule(
        organization_id=1,
        kind=RecoveryKind.CALL_RETRY,
        reason="test_failure",
        workflow_run_id=99,
        session_id="s1",
    )
    assert job is not None
    assert job.kind == RecoveryKind.CALL_RETRY
    fake.zadd.assert_called()


@pytest.mark.asyncio
async def test_event_store_idempotency_local():
    from api.services.call_reliability.event_store import DurableEventStore

    store = DurableEventStore()
    store._redis = None  # noqa: SLF001 — force local-only path
    with patch.object(store, "_get_redis", side_effect=RuntimeError("no redis")):
        e1 = await store.append_simple(
            ReliabilityEventType.TRANSCRIPT,
            organization_id=1,
            session_id="s1",
            payload={"text": "hello"},
            idempotency_key="idem-1",
        )
        e2 = await store.append_simple(
            ReliabilityEventType.TRANSCRIPT,
            organization_id=1,
            session_id="s1",
            payload={"text": "hello"},
            idempotency_key="idem-1",
        )
    assert e1.event_id == e2.event_id


@pytest.mark.asyncio
async def test_recovery_worker_records_failure():
    from api.services.call_reliability.recovery_workers import RecoveryWorkerService

    worker = RecoveryWorkerService()
    with patch(
        "api.services.call_reliability.recovery_workers.get_call_retry_queue"
    ) as mock_queue:
        mock_queue.return_value.schedule = AsyncMock(
            return_value=type("J", (), {"job_id": "job-1"})()
        )
        with patch(
            "api.services.call_reliability.recovery_workers.get_durable_event_store"
        ) as mock_store:
            mock_store.return_value.append_simple = AsyncMock()
            with patch(
                "api.services.call_reliability.recovery_workers.get_failure_monitor"
            ) as mock_monitor:
                mock_monitor.return_value.record = AsyncMock()
                result = await worker.record_call_failure(
                    organization_id=1,
                    reason="dispatch_failed",
                    workflow_run_id=10,
                    session_id="sess",
                )
    assert result["recorded"] is True


def test_prerecorded_not_needed_here():
    from api.services.call_reliability.types import FailureSeverity

    assert FailureSeverity.CRITICAL.value == "critical"
