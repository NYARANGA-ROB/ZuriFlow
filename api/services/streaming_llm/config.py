"""Configuration for realtime streaming LLM."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamingLLMConfig:
    model: str = "gpt-4o-mini-realtime-preview"
    base_url: str = "wss://api.openai.com/v1/realtime"
    output_modalities: tuple[str, ...] = ("text",)

    # Queues
    event_queue_maxsize: int = 256
    input_queue_maxsize: int = 32
    queue_put_timeout_s: float = 0.05

    # Partial sentence streaming (for TTS chunking)
    min_sentence_chars: int = 12
    sentence_delimiters: str = ".?!\n"
    emit_partial_on_delimiter: bool = True

    # Conversation memory
    max_messages: int = 40
    max_context_chars: int = 32_000

    # Connection / recovery
    connect_timeout_s: float = 10.0
    generation_idle_timeout_s: float = 60.0
    max_reconnect_attempts: int = 3
    reconnect_backoff_s: float = 0.5

    # Low latency
    temperature: float = 0.8
    max_output_tokens: int | None = 1024


DEFAULT_STREAMING_LLM_CONFIG = StreamingLLMConfig()
