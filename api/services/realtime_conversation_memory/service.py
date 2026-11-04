"""Realtime conversation memory orchestrator."""

from __future__ import annotations

from api.services.realtime_conversation_memory.config import DEFAULT_MEMORY_CONFIG, RealtimeMemoryConfig
from api.services.realtime_conversation_memory.intent import IntentTracker
from api.services.realtime_conversation_memory.retrieval import AsyncRetrievalService
from api.services.realtime_conversation_memory.state import ConversationStateManager
from api.services.realtime_conversation_memory.store import MemoryStore
from api.services.realtime_conversation_memory.summarizer import ContextSummarizer
from api.services.realtime_conversation_memory.types import (
    CallIntent,
    MemorySnapshot,
    RetrievalResult,
)
from api.services.voice_pipeline.types import LLMMessage


class RealtimeConversationMemoryService:
    """Per-session conversation memory for voice calls."""

    def __init__(self, config: RealtimeMemoryConfig = DEFAULT_MEMORY_CONFIG) -> None:
        self._config = config
        self._store = MemoryStore(config)
        self._intent = IntentTracker(config)
        self._summarizer = ContextSummarizer(config)
        self._retrieval = AsyncRetrievalService(config, self._store)
        self._managers: dict[str, ConversationStateManager] = {}

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def session(self, session_id: str) -> ConversationStateManager:
        if session_id not in self._managers:
            mgr = ConversationStateManager(
                session_id,
                self._store,
                self._intent,
                self._summarizer,
                self._config,
            )
            self._managers[session_id] = mgr
            self._retrieval.bind(mgr)
        return self._managers[session_id]

    async def prepare_messages(
        self,
        session_id: str,
        messages: list[LLMMessage],
    ) -> tuple[list[LLMMessage], RetrievalResult]:
        if not self._config.enabled:
            return messages, RetrievalResult(
                session_id=session_id,
                context_block="",
                summary="",
                intent=CallIntent.UNKNOWN,
                intent_confidence=0.0,
                slots={},
                recent_turns=[],
                latency_ms=0.0,
            )

        result = await self._retrieval.retrieve_with_timeout(session_id)
        if self._config.inject_context_as_system_hint:
            enriched = self._retrieval.inject_context(messages, result)
            return enriched, result
        return messages, result

    def end_session(self, session_id: str) -> MemorySnapshot | None:
        mgr = self._managers.pop(session_id, None)
        self._retrieval.unbind(session_id)
        if mgr is None:
            return None
        return mgr.close()


_service: RealtimeConversationMemoryService | None = None


def get_conversation_memory_service() -> RealtimeConversationMemoryService:
    global _service
    if _service is None:
        _service = RealtimeConversationMemoryService()
    return _service
