"""Async low-latency context retrieval for LLM turns."""

from __future__ import annotations

import asyncio
import time

from api.services.realtime_conversation_memory.config import RealtimeMemoryConfig
from api.services.realtime_conversation_memory.state import ConversationStateManager
from api.services.realtime_conversation_memory.store import MemoryStore
from api.services.realtime_conversation_memory.types import CallIntent, MemorySnapshot, RetrievalResult
from api.services.voice_pipeline.types import LLMMessage


class AsyncRetrievalService:
    """Retrieve conversation context with bounded latency."""

    def __init__(self, config: RealtimeMemoryConfig, store: MemoryStore) -> None:
        self._config = config
        self._store = store
        self._managers: dict[str, ConversationStateManager] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def bind(self, manager: ConversationStateManager) -> None:
        self._managers[manager.session_id] = manager
        self._locks.setdefault(manager.session_id, asyncio.Lock())

    def unbind(self, session_id: str) -> None:
        self._managers.pop(session_id, None)
        self._locks.pop(session_id, None)

    async def retrieve(self, session_id: str) -> RetrievalResult:
        start = time.perf_counter()
        lock = self._locks.setdefault(session_id, asyncio.Lock())

        async with lock:
            manager = self._managers.get(session_id)
            if manager is not None:
                recovered = manager.on_pause_tick()
                snap = manager.snapshot()
            else:
                recovered = False
                mem = self._store.get(session_id)
                if mem is None:
                    elapsed = (time.perf_counter() - start) * 1000.0
                    return RetrievalResult(
                        session_id=session_id,
                        context_block="",
                        summary="",
                        intent=CallIntent.UNKNOWN,
                        intent_confidence=0.0,
                        slots={},
                        recent_turns=[],
                        latency_ms=elapsed,
                    )
                from api.services.realtime_conversation_memory.types import MemorySnapshot

                snap = MemorySnapshot(
                    session_id=session_id,
                    turns=list(mem.turns),
                    summary=mem.summary,
                    intent=mem.intent,
                    interrupted=mem.interrupted,
                    partial_assistant=mem.partial_assistant,
                    pause_duration_s=self._store.pause_elapsed_s(session_id),
                    last_activity=mem.last_activity,
                )

            context = self._format_context(snap, recovered_from_pause=recovered)
            elapsed = (time.perf_counter() - start) * 1000.0
            return RetrievalResult(
                session_id=session_id,
                context_block=context,
                summary=snap.summary,
                intent=snap.intent.current,
                intent_confidence=snap.intent.confidence,
                slots=dict(snap.intent.slots),
                recent_turns=snap.turns[-4:],
                latency_ms=elapsed,
                recovered_from_pause=recovered,
            )

    async def retrieve_with_timeout(self, session_id: str) -> RetrievalResult:
        timeout = self._config.retrieval_timeout_ms / 1000.0
        try:
            return await asyncio.wait_for(self.retrieve(session_id), timeout=timeout)
        except asyncio.TimeoutError:
            return RetrievalResult(
                session_id=session_id,
                context_block="",
                summary="",
                intent=CallIntent.UNKNOWN,
                intent_confidence=0.0,
                slots={},
                recent_turns=[],
                latency_ms=self._config.retrieval_timeout_ms,
            )

    def inject_context(
        self,
        messages: list[LLMMessage],
        result: RetrievalResult,
    ) -> list[LLMMessage]:
        if not result.context_block:
            return messages
        hint = LLMMessage(
            role="system",
            content=f"[Conversation memory]\n{result.context_block}",
        )
        return [hint, *messages]

    def _format_context(self, snap, *, recovered_from_pause: bool) -> str:
        lines: list[str] = []
        if snap.summary:
            lines.append(f"Summary: {snap.summary}")
        if snap.intent.current != CallIntent.UNKNOWN:
            lines.append(
                f"Caller intent: {snap.intent.current.value} "
                f"(confidence {snap.intent.confidence:.2f})"
            )
        if snap.intent.slots:
            slots = ", ".join(f"{k}={v}" for k, v in snap.intent.slots.items())
            lines.append(f"Slots: {slots}")
        if snap.interrupted and snap.partial_assistant:
            lines.append(
                f"Interrupted: bot was saying \"{snap.partial_assistant[:120]}\""
            )
        if recovered_from_pause and snap.pause_duration_s > 0:
            lines.append(
                f"Caller paused {snap.pause_duration_s:.0f}s — resume naturally without repeating everything."
            )
        for turn in snap.turns[-3:]:
            if turn.user_text:
                lines.append(f"Caller: {turn.user_text}")
            if turn.assistant_text and not turn.interrupted:
                lines.append(f"Agent: {turn.assistant_text}")
        return "\n".join(lines)
