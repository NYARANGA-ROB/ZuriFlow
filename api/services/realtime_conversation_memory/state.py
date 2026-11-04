"""Conversation state manager — short-term call state with interruption support."""

from __future__ import annotations

from api.services.realtime_conversation_memory.config import RealtimeMemoryConfig
from api.services.realtime_conversation_memory.intent import IntentTracker
from api.services.realtime_conversation_memory.store import MemoryStore
from api.services.realtime_conversation_memory.summarizer import ContextSummarizer
from api.services.realtime_conversation_memory.types import MemorySnapshot, TurnRecord
from api.services.voice_pipeline.types import LLMMessage


class ConversationStateManager:
    """Manages short-term conversation state for one voice call session."""

    def __init__(
        self,
        session_id: str,
        store: MemoryStore,
        intent_tracker: IntentTracker,
        summarizer: ContextSummarizer,
        config: RealtimeMemoryConfig,
    ) -> None:
        self._session_id = session_id
        self._store = store
        self._intent_tracker = intent_tracker
        self._summarizer = summarizer
        self._config = config

    @property
    def session_id(self) -> str:
        return self._session_id

    def on_user_turn(self, text: str) -> TurnRecord:
        mem = self._store.get_or_create(self._session_id)
        intent = self._intent_tracker.update(text, mem.intent)
        self._store.set_intent(self._session_id, intent)
        turn = self._store.begin_turn(self._session_id, text)
        turn.intent = intent.current
        return turn

    def on_assistant_complete(self, text: str, *, interrupted: bool = False) -> TurnRecord | None:
        turn = self._store.complete_turn(
            self._session_id, text, interrupted=interrupted
        )
        if turn is not None:
            self._refresh_summary()
        if not interrupted:
            self._store.clear_interrupt(self._session_id)
        return turn

    def on_interruption(self, partial_assistant: str = "") -> None:
        mem = self._store.get_or_create(self._session_id)
        intent = self._intent_tracker.mark_interruption(mem.intent)
        self._store.set_intent(self._session_id, intent)
        self._store.mark_interrupted(self._session_id, partial_assistant)
        self._refresh_summary()

    def on_pause_tick(self) -> bool:
        """Returns True if pause exceeded recovery threshold."""
        pause_s = self._store.pause_elapsed_s(self._session_id)
        if pause_s < self._config.pause_recovery_s:
            return False
        mem = self._store.get(self._session_id)
        if mem is None:
            return False
        compressed = self._summarizer.compress_turns(list(mem.turns), mem.intent)
        self._store.set_summary(self._session_id, compressed)
        return True

    def snapshot(self) -> MemorySnapshot:
        mem = self._store.get_or_create(self._session_id)
        pause_s = self._store.pause_elapsed_s(self._session_id)
        return MemorySnapshot(
            session_id=self._session_id,
            turns=list(mem.turns),
            summary=mem.summary,
            intent=mem.intent,
            interrupted=mem.interrupted,
            partial_assistant=mem.partial_assistant,
            pause_duration_s=pause_s,
            last_activity=mem.last_activity,
        )

    def messages_for_llm(self, base_messages: list[LLMMessage]) -> list[LLMMessage]:
        return list(base_messages)

    def _refresh_summary(self) -> None:
        mem = self._store.get(self._session_id)
        if mem is None:
            return
        summary = self._summarizer.summarize(
            list(mem.turns),
            mem.intent,
            prior_summary=mem.summary,
            partial_assistant=mem.partial_assistant,
            interrupted=mem.interrupted,
        )
        self._store.set_summary(self._session_id, summary)

    def close(self) -> MemorySnapshot:
        snap = self.snapshot()
        self._store.remove(self._session_id)
        return snap
