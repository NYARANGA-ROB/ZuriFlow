"""Low-latency provider tuning profiles."""

from __future__ import annotations

from dataclasses import replace

from api.services.streaming_llm.config import DEFAULT_STREAMING_LLM_CONFIG, StreamingLLMConfig
from api.services.streaming_stt.config import DEFAULT_STREAMING_STT_CONFIG, StreamingSTTConfig
from api.services.streaming_tts.config import DEFAULT_STREAMING_TTS_CONFIG, StreamingTTSConfig

LOW_LATENCY_STT_CONFIG = replace(
    DEFAULT_STREAMING_STT_CONFIG,
    audio_queue_maxsize=8,
    transcript_queue_maxsize=16,
    audio_put_timeout_s=0.0,
    deepgram_endpointing_ms=80,
    deepgram_utterance_end_ms=700,
    deepgram_interim_results=True,
)

LOW_LATENCY_LLM_CONFIG = replace(
    DEFAULT_STREAMING_LLM_CONFIG,
    event_queue_maxsize=32,
    input_queue_maxsize=8,
    queue_put_timeout_s=0.0,
    min_sentence_chars=4,
    emit_partial_on_delimiter=True,
    temperature=0.7,
    max_output_tokens=512,
)

LOW_LATENCY_TTS_CONFIG = replace(
    DEFAULT_STREAMING_TTS_CONFIG,
    text_queue_maxsize=16,
    audio_queue_maxsize=8,
    queue_put_timeout_s=0.0,
    min_playback_buffer_ms=10,
    max_playback_buffer_ms=120,
    elevenlabs_optimize_latency=4,
)
