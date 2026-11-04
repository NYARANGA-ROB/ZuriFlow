"""Configuration for realtime streaming STT."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StreamingSTTConfig:
    sample_rate: int = 16000
    channels: int = 1
    encoding: str = "linear16"

    # Queues
    audio_queue_maxsize: int = 64
    transcript_queue_maxsize: int = 128
    audio_put_timeout_s: float = 0.05

    # Deepgram
    deepgram_model: str = "nova-3-general"
    deepgram_language: str = "multi"
    deepgram_endpointing_ms: int = 100
    deepgram_utterance_end_ms: int = 1000
    deepgram_interim_results: bool = True
    deepgram_keyterms: tuple[str, ...] = ()

    # Whisper fallback (OpenAI-compatible transcription API)
    whisper_model: str = "whisper-1"
    whisper_base_url: str = "https://api.openai.com/v1"
    whisper_min_buffer_ms: int = 500
    whisper_max_buffer_ms: int = 8000

    # Recovery
    deepgram_connect_timeout_s: float = 5.0
    deepgram_idle_timeout_s: float = 8.0
    deepgram_reconnect_attempts: int = 2
    fallback_after_reconnect_fail: bool = True
    watchdog_interval_s: float = 1.0

    # Interruption
    interrupt_clear_buffer: bool = True


DEFAULT_STREAMING_STT_CONFIG = StreamingSTTConfig()
