"""Async metrics collector implementation."""

from __future__ import annotations

import asyncio
import time

from loguru import logger

from api.services.voice_pipeline.metrics.interfaces import (
    MetricEvent,
    MetricName,
    MetricsCollector,
    MetricsSnapshot,
)


class AsyncMetricsCollector:
    """Buffers metrics in a background task to keep the hot path non-blocking."""

    def __init__(self, workflow_run_id: int) -> None:
        self._workflow_run_id = workflow_run_id
        self._queue: asyncio.Queue[MetricEvent | None] = asyncio.Queue()
        self._events: list[MetricEvent] = []
        self._counters: dict[str, float] = {}
        self._durations_ms: dict[str, float] = {}
        self._worker: asyncio.Task | None = None

    async def start(self) -> None:
        self._worker = asyncio.create_task(self._consume())

    async def stop(self) -> None:
        await self._queue.put(None)
        if self._worker:
            await self._worker

    async def record(self, event: MetricEvent) -> None:
        await self._queue.put(event)

    def record_fast(self, event: MetricEvent) -> None:
        """Non-blocking metric enqueue for hot-path latency marks."""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def snapshot(self) -> MetricsSnapshot:
        return MetricsSnapshot(
            workflow_run_id=self._workflow_run_id,
            events=list(self._events),
            counters=dict(self._counters),
            durations_ms=dict(self._durations_ms),
        )

    async def _consume(self) -> None:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            self._events.append(event)
            key = event.name.value
            self._counters[key] = self._counters.get(key, 0.0) + 1.0
            if event.value is not None:
                self._durations_ms[key] = event.value
            logger.debug(
                f"[metrics run={event.workflow_run_id}] {event.name.value} "
                f"labels={event.labels}"
            )


def now_ms() -> float:
    return time.time() * 1000.0


async def record_stage(
    collector: MetricsCollector,
    *,
    workflow_run_id: int,
    stage: str,
    started_ms: float,
) -> None:
    await collector.record(
        MetricEvent(
            name=MetricName.STAGE_DURATION,
            workflow_run_id=workflow_run_id,
            timestamp_ms=now_ms(),
            value=now_ms() - started_ms,
            labels={"stage": stage},
        )
    )


def metric(
    name: MetricName,
    workflow_run_id: int,
    *,
    value: float | None = None,
    labels: dict[str, str] | None = None,
) -> MetricEvent:
    return MetricEvent(
        name=name,
        workflow_run_id=workflow_run_id,
        timestamp_ms=now_ms(),
        value=value,
        labels=labels or {},
    )
