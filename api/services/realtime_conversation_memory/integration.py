"""Integration with the realtime voice pipeline."""

from __future__ import annotations

from api.constants import REALTIME_MEMORY_ENABLED
from api.services.realtime_conversation_memory.service import (
    RealtimeConversationMemoryService,
    get_conversation_memory_service,
)


def get_call_memory(session_id: str) -> RealtimeConversationMemoryService | None:
    if not REALTIME_MEMORY_ENABLED:
        return None
    return get_conversation_memory_service()
