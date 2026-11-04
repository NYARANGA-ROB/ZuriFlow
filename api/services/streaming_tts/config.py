"""Configuration for low-latency streaming TTS."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamingTTSConfig:
    sample_rate: int = 16000
    channels: int = 1

    # ElevenLabs
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_model: str = "eleven_flash_v2_5"
    elevenlabs_voice_id: str = ""
    elevenlabs_stability: float = 0.5
    elevenlabs_similarity_boost: float = 0.75
    elevenlabs_speed: float = 1.0
    elevenlabs_optimize_latency: int = 4  # 0-4, higher = lower latency
    elevenlabs_output_format: str = "pcm_16000"

    # Queues
    text_queue_maxsize: int = 64
    audio_queue_maxsize: int = 48
    queue_put_timeout_s: float = 0.05

    # Playback buffer (jitter / pre-roll)
    min_playback_buffer_ms: int = 40
    max_playback_buffer_ms: int = 500
    max_chunk_bytes: int = 16384

    # Connection
    connect_timeout_s: float = 5.0
    synthesis_idle_timeout_s: float = 30.0
    max_reconnect_attempts: int = 3
    reconnect_backoff_s: float = 0.5


DEFAULT_STREAMING_TTS_CONFIG = StreamingTTSConfig()
