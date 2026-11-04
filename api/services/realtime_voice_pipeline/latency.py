"""Non-blocking per-turn latency measurement for the voice pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from api.services.voice_pipeline.metrics.interfaces import MetricName, MetricsCollector
from api.services.voice_pipeline.metrics.service import metric, now_ms


@dataclass
class LatencyMark:
    name: str
    monotonic_ms: float
    wall_ms: float


@dataclass
class PipelineLatencyTracker:
    """Tracks stage timestamps for one user→bot turn without blocking the hot path."""

    workflow_run_id: int
    metrics: MetricsCollector | None = None
    session_id: str = ""
    organization_id: int = 0
    _turn_id: int = 0
    _marks: dict[str, LatencyMark] = field(default_factory=dict)
    _turn_started_mono: float | None = None

    def begin_turn(self, *, trigger: str = "stt_final") -> int:
        self._turn_id += 1
        self._marks.clear()
        self._turn_started_mono = time.monotonic()
        self.mark("turn_start", metadata={"trigger": trigger})
        return self._turn_id

    def mark(self, name: str, *, metadata: dict[str, Any] | None = None) -> None:
        mono = time.monotonic()
        self._marks[name] = LatencyMark(name=name, monotonic_ms=mono * 1000.0, wall_ms=now_ms())
        if self.metrics is not None:
            self._emit_metric(name, metadata or {})
            obs = getattr(self.metrics, "record_turn_stage", None)
            if obs is not None and name in (
                "stt_final",
                "normalize",
                "intent",
                "workflow",
                "tool_call",
                "llm_first_token",
                "tts_first_text",
                "tts_first_byte",
                "outbound_first_byte",
            ):
                value_ms = self.since_turn_start_ms()
                if value_ms is not None:
                    self.metrics.record_turn_stage(name, value_ms=value_ms)

    def mark_duration(self, name: str, value_ms: float) -> None:
        mono = time.monotonic()
        self._marks[name] = LatencyMark(name=name, monotonic_ms=mono * 1000.0, wall_ms=now_ms())
        obs = getattr(self.metrics, "record_turn_stage", None) if self.metrics else None
        if obs is not None:
            obs(name, value_ms=value_ms)

    def since_turn_start_ms(self) -> float | None:
        if self._turn_started_mono is None:
            return None
        return (time.monotonic() - self._turn_started_mono) * 1000.0

    def delta_ms(self, start: str, end: str) -> float | None:
        a = self._marks.get(start)
        b = self._marks.get(end)
        if not a or not b:
            return None
        return b.monotonic_ms - a.monotonic_ms

    def record_turn_complete(self) -> dict[str, float | None]:
        """Emit end-to-end and stage metrics; return computed deltas."""
        e2e = self.since_turn_start_ms()
        stages = {
            "stt_to_normalize_ms": self.delta_ms("stt_final", "normalize"),
            "normalize_to_intent_ms": self.delta_ms("normalize", "intent"),
            "stt_to_llm_start_ms": self.delta_ms("turn_start", "llm_first_token"),
            "llm_to_tts_start_ms": self.delta_ms("llm_first_token", "tts_first_text"),
            "tts_to_audio_ms": self.delta_ms("tts_first_text", "tts_first_byte"),
            "audio_to_outbound_ms": self.delta_ms("tts_first_byte", "outbound_first_byte"),
            "tool_call_ms": self.delta_ms("tool_start", "tool_done"),
            "turn_e2e_ms": e2e,
        }
        if self.metrics is not None and e2e is not None:
            self._emit_metric(
                "turn_e2e",
                {"session_id": self.session_id, "turn_id": str(self._turn_id)},
                value=e2e,
                metric_name=MetricName.USER_TO_BOT_LATENCY,
            )
            record_complete = getattr(self.metrics, "record_turn_complete", None)
            if record_complete is not None:
                record_complete(stages)
            else:
                for key, value in stages.items():
                    if value is not None:
                        self._emit_metric(
                            key,
                            {"session_id": self.session_id, "turn_id": str(self._turn_id)},
                            value=value,
                            metric_name=MetricName.STAGE_DURATION,
                        )
        if e2e is not None and self.organization_id > 0:
            from api.services.voice_analytics.integration import track_response_latency

            track_response_latency(
                organization_id=self.organization_id,
                session_id=self.session_id,
                workflow_run_id=self.workflow_run_id,
                e2e_ms=e2e,
                stages=stages,
            )
        return stages

    def _emit_metric(
        self,
        stage: str,
        labels: dict[str, str],
        *,
        value: float | None = None,
        metric_name: MetricName | None = None,
    ) -> None:
        if self.metrics is None:
            return
        name = metric_name or MetricName.STAGE_DURATION
        event = metric(
            name,
            self.workflow_run_id,
            value=value,
            labels={**labels, "stage": stage},
        )
        record_fast = getattr(self.metrics, "record_fast", None)
        if record_fast is not None:
            record_fast(event)
        else:
            # Fallback — schedule without awaiting on hot path.
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.metrics.record(event))
            except RuntimeError:
                pass
