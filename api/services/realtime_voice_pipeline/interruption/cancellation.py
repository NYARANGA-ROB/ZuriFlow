"""Ordered cancellation: TTS stop → LLM pause → STT restart → recovery."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol

from loguru import logger

from api.services.realtime_voice_pipeline.interruption.detector import InterruptionEvent
from api.services.realtime_voice_pipeline.interruption.recovery import (
    ConversationRecoveryManager,
)
from api.services.realtime_voice_pipeline.interruption.tts_stop import TTSStopHandler
from api.services.realtime_voice_pipeline.queues import PipelineQueues


class InterruptibleLLM(Protocol):
    async def interrupt(self) -> None: ...


class InterruptibleSTT(Protocol):
    async def interrupt(self) -> None: ...


@dataclass
class InterruptionCancellationManager:
    """Coordinates barge-in across TTS, LLM, STT, and conversation recovery."""

    llm: InterruptibleLLM | None = None
    stt: InterruptibleSTT | None = None
    tts_stop: TTSStopHandler | None = None
    recovery: ConversationRecoveryManager | None = None
    queues: PipelineQueues | None = None
    session_id: str = ""
    organization_id: int = 0
    workflow_run_id: int = 0

    bot_speaking: bool = False
    llm_active: bool = False
    tts_generation_id: str | None = None
    llm_generation_id: str | None = None
    interrupted: bool = False
    recovery_handled: bool = False

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _interrupt_count: int = 0
    _turn_cancelled: asyncio.Event = field(default_factory=asyncio.Event)

    def mark_bot_speaking(self, *, generation_id: str | None = None) -> None:
        self.bot_speaking = True
        if generation_id:
            self.tts_generation_id = generation_id

    def mark_bot_idle(self) -> None:
        self.bot_speaking = False
        self.tts_generation_id = None

    def mark_llm_active(self, *, generation_id: str | None = None) -> None:
        self.llm_active = True
        self.interrupted = False
        self.recovery_handled = False
        self._turn_cancelled.clear()
        if generation_id:
            self.llm_generation_id = generation_id

    def mark_llm_idle(self) -> None:
        self.llm_active = False
        self.llm_generation_id = None

    @property
    def should_barge_in(self) -> bool:
        return self.bot_speaking or self.llm_active

    def is_turn_cancelled(self) -> bool:
        return self._turn_cancelled.is_set()

    async def handle_interruption(self, event: InterruptionEvent) -> dict[str, Any]:
        """Execute ordered cancellation and prepare for natural conversation resume."""
        async with self._lock:
            if not self.should_barge_in and event.source.value != "external":
                return {"cancelled": False, "reason": event.reason}

            self._interrupt_count += 1
            self.interrupted = True
            self._turn_cancelled.set()
            stages: list[str] = []
            partial = self.recovery.partial_assistant_text() if self.recovery else ""

            # 1. Stop TTS immediately (highest priority).
            if self.tts_stop is not None and (self.bot_speaking or self.tts_generation_id):
                try:
                    await self.tts_stop.stop_immediately(self.tts_generation_id)
                    stages.append("tts")
                except Exception as e:
                    logger.warning("interruption TTS stop failed: {}", e)

            # 2. Pause / cancel LLM generation.
            if self.llm is not None and self.llm_active:
                try:
                    await self.llm.interrupt()
                    stages.append("llm")
                except Exception as e:
                    logger.warning("interruption LLM pause failed: {}", e)

            # 3. Flush any remaining outbound audio.
            if self.queues is not None:
                flushed = self.queues.flush_outbound()
                if flushed:
                    stages.append(f"outbound_flush:{flushed}")

            # 4. Restart STT listening (clear buffers).
            if self.stt is not None:
                try:
                    await self.stt.interrupt()
                    stages.append("stt_restart")
                except Exception as e:
                    logger.warning("interruption STT restart failed: {}", e)

            # 5. Conversation recovery.
            if self.recovery is not None:
                self.recovery.on_interruption(partial_assistant=partial or None)
                self.recovery.resume_after_interrupt()
                self.recovery_handled = True
                stages.append("recovery")

            self.mark_llm_idle()
            self.mark_bot_idle()

            logger.info(
                "caller interruption source={} reason={} stages={} count={}",
                event.source.value,
                event.reason,
                stages,
                self._interrupt_count,
            )
            from api.services.realtime_observability.collector import (
                VoiceObservabilityCollector,
            )

            VoiceObservabilityCollector.record_interruption(
                source=event.source.value,
                session_id=self.session_id,
            )
            if self.organization_id > 0:
                from api.services.voice_analytics.integration import track_interruption

                track_interruption(
                    organization_id=self.organization_id,
                    session_id=self.session_id,
                    workflow_run_id=self.workflow_run_id,
                    source=event.source.value,
                    interrupt_count=self._interrupt_count,
                )
            return {
                "cancelled": bool(stages),
                "reason": event.reason,
                "source": event.source.value,
                "stages": stages,
                "count": self._interrupt_count,
            }

    async def interrupt_all(self, *, reason: str = "barge_in") -> dict[str, Any]:
        """Backward-compatible entry point used by control handlers."""
        from api.services.realtime_voice_pipeline.interruption.detector import (
            InterruptionSource,
        )

        return await self.handle_interruption(
            InterruptionEvent(source=InterruptionSource.EXTERNAL, reason=reason)
        )
