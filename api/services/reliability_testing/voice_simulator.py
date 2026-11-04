from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from api.services.realtime_voice_pipeline.config import RealtimeVoicePipelineConfig
from api.services.realtime_voice_pipeline.interruption.cancellation import (
    InterruptionCancellationManager,
)
from api.services.realtime_voice_pipeline.interruption.detector import (
    InterruptionEvent,
    InterruptionDetector,
    InterruptionSource,
)
from api.services.realtime_voice_pipeline.interruption.recovery import ConversationRecoveryManager
from api.services.realtime_voice_pipeline.queues import PipelineQueues
from api.services.reliability_testing.concurrent_simulator import ConcurrentSimulator
from api.services.reliability_testing.types import OperationResult, ScenarioResult, StressScenario
from api.services.voice_pipeline.types import TranscriptEvent, TranscriptKind


@dataclass
class VoiceCallSessionSimulator:
    """In-process simulator for concurrent voice call turns."""

    concurrent_sessions: int = 20
    turns_per_session: int = 3
    interrupt_every_n_turns: int = 2

    async def run(self) -> ScenarioResult:
        result = ScenarioResult(scenario=StressScenario.CONCURRENT_CALLS)
        result.metadata = {
            "concurrent_sessions": self.concurrent_sessions,
            "turns_per_session": self.turns_per_session,
        }

        async def _session(session_idx: int) -> OperationResult:
            start = time.perf_counter()
            cfg = RealtimeVoicePipelineConfig(session_id=f"load-sess-{session_idx}")
            queues = PipelineQueues(cfg)
            recovery = ConversationRecoveryManager()
            llm = _AsyncInterruptible()
            stt = _AsyncInterruptible()
            cancellation = InterruptionCancellationManager(
                llm=llm,
                stt=stt,
                recovery=recovery,
                queues=queues,
                session_id=cfg.session_id,
                organization_id=1,
            )
            detector = InterruptionDetector(
                config=cfg,
                is_bot_active=lambda: cancellation.should_barge_in,
            )
            interruptions = 0
            try:
                for turn in range(self.turns_per_session):
                    user_text = f"Turn {turn} from session {session_idx}"
                    recovery.append_user(user_text)
                    cancellation.mark_llm_active()
                    cancellation.mark_bot_speaking(generation_id=f"tts-{turn}")
                    recovery.begin_assistant_turn()
                    recovery.append_assistant_delta("Bot response partial")

                    if self.interrupt_every_n_turns and turn % self.interrupt_every_n_turns == 1:
                        event = detector.on_transcript(
                            TranscriptEvent(kind=TranscriptKind.PARTIAL, text="wait stop")
                        )
                        if event:
                            await cancellation.handle_interruption(event)
                            interruptions += 1

                    final = TranscriptEvent(kind=TranscriptKind.FINAL, text=user_text)
                    queues.put_transcript(final)
                    cancellation.mark_bot_idle()
                    cancellation.mark_llm_idle()

                op = OperationResult(
                    name=f"session-{session_idx}",
                    success=True,
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    metadata={"interruptions": interruptions, "turns": self.turns_per_session},
                )
                result.record(op)
                return op
            except Exception as exc:
                op = OperationResult(
                    name=f"session-{session_idx}",
                    success=False,
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    error=str(exc),
                )
                result.record(op)
                return op
            finally:
                await queues.close()

        sim = ConcurrentSimulator(workers=self.concurrent_sessions, ramp_up_s=2.0)
        await sim.run(_session)
        result.finish()
        return result


@dataclass
class InterruptionBurstSimulator:
    """Stress interruption handling with rapid barge-in events."""

    burst_count: int = 30
    concurrent_handlers: int = 5

    async def run(self) -> ScenarioResult:
        result = ScenarioResult(scenario=StressScenario.INTERRUPTION_BURST)
        result.metadata = {"burst_count": self.burst_count}

        async def _handler(handler_id: int) -> OperationResult:
            start = time.perf_counter()
            cfg = RealtimeVoicePipelineConfig(session_id=f"intr-{handler_id}")
            recovery = ConversationRecoveryManager()
            llm = _AsyncInterruptible()
            stt = _AsyncInterruptible()
            mgr = InterruptionCancellationManager(
                llm=llm,
                stt=stt,
                recovery=recovery,
                organization_id=1,
            )
            mgr.mark_llm_active()
            mgr.mark_bot_speaking()
            recovery.begin_assistant_turn()
            recovery.append_assistant_delta("Speaking...")

            events_per = self.burst_count // self.concurrent_handlers
            cancelled = 0
            for _ in range(events_per):
                out = await mgr.handle_interruption(
                    InterruptionEvent(source=InterruptionSource.VAD, reason="burst")
                )
                if out.get("cancelled"):
                    cancelled += 1
                mgr.mark_llm_active()
                mgr.mark_bot_speaking()

            op = OperationResult(
                name=f"handler-{handler_id}",
                success=cancelled > 0,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                metadata={"cancelled": cancelled},
            )
            result.record(op)
            return op

        sim = ConcurrentSimulator(workers=self.concurrent_handlers, ramp_up_s=0.2)
        await sim.run(_handler)
        result.finish()
        return result


class _AsyncInterruptible:
    async def interrupt(self) -> None:
        await asyncio.sleep(0)
