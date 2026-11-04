"""Streaming LLM errors."""

from __future__ import annotations


class StreamingLLMError(Exception):
    def __init__(self, message: str, *, code: str = "llm_error") -> None:
        super().__init__(message)
        self.code = code


class RealtimeConnectionError(StreamingLLMError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="realtime_connection_error")


class GenerationCancelledError(StreamingLLMError):
    def __init__(self, generation_id: str) -> None:
        super().__init__(
            f"generation cancelled: {generation_id}", code="generation_cancelled"
        )
        self.generation_id = generation_id


class ConversationStateError(StreamingLLMError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="conversation_state_error")
