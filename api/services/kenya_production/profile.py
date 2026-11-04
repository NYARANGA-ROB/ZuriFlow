"""Kenya production deployment profiles and tuning."""

from __future__ import annotations

from dataclasses import replace

from api.constants import KENYA_PRODUCTION_MODE
from api.services.realtime_voice_pipeline.config import (
    LOW_LATENCY_PIPELINE_CONFIG,
    RealtimeVoicePipelineConfig,
)
from api.services.realtime_voice_pipeline.low_latency_profiles import (
    LOW_LATENCY_LLM_CONFIG,
    LOW_LATENCY_STT_CONFIG,
    LOW_LATENCY_TTS_CONFIG,
)
from api.services.streaming_llm.config import StreamingLLMConfig
from api.services.streaming_stt.config import StreamingSTTConfig
from api.services.streaming_tts.config import StreamingTTSConfig

# Tighter queues + VAD for Kenyan mobile networks (reduce buffer bloat).
KENYA_PRODUCTION_PIPELINE_CONFIG = replace(
    LOW_LATENCY_PIPELINE_CONFIG,
    inbound_audio_maxsize=3,
    transcript_maxsize=6,
    outbound_audio_maxsize=2,
    llm_event_maxsize=16,
    vad_hangover_frames=2,
    interrupt_cooldown_s=0.18,
    min_partial_chars_for_barge_in=2,
    target_e2e_latency_ms=650,
    prefetch_tts_on_turn=True,
)

# Shorter utterance end → faster finals; slightly higher endpointing stability on GSM.
KENYA_PRODUCTION_STT_CONFIG = replace(
    LOW_LATENCY_STT_CONFIG,
    deepgram_endpointing_ms=60,
    deepgram_utterance_end_ms=550,
    audio_queue_maxsize=6,
    transcript_queue_maxsize=8,
)

# Cap tokens for cost control on high-volume Kenyan deployments.
KENYA_PRODUCTION_LLM_CONFIG = replace(
    LOW_LATENCY_LLM_CONFIG,
    max_output_tokens=384,
    min_sentence_chars=3,
    input_queue_maxsize=4,
    event_queue_maxsize=24,
)

# Minimize TTS buffer for voice-first UX.
KENYA_PRODUCTION_TTS_CONFIG = replace(
    LOW_LATENCY_TTS_CONFIG,
    min_playback_buffer_ms=8,
    max_playback_buffer_ms=90,
    audio_queue_maxsize=6,
    elevenlabs_optimize_latency=4,
)


def resolve_pipeline_config(base: RealtimeVoicePipelineConfig) -> RealtimeVoicePipelineConfig:
    if not KENYA_PRODUCTION_MODE:
        return base
    return replace(
        KENYA_PRODUCTION_PIPELINE_CONFIG,
        session_id=base.session_id,
        sample_rate=base.sample_rate,
        channels=base.channels,
        system_prompt=base.system_prompt,
        kenyan_conversation_enabled=base.kenyan_conversation_enabled,
        kenyan_domain=base.kenyan_domain,
        realtime_memory_enabled=base.realtime_memory_enabled,
        kenyan_intent_enabled=base.kenyan_intent_enabled,
        call_routing_enabled=base.call_routing_enabled,
        voice_mpesa_enabled=base.voice_mpesa_enabled,
        organization_id=base.organization_id,
        phone_e164=base.phone_e164,
        customer_name=base.customer_name,
        payment_amount=base.payment_amount,
        payment_language=base.payment_language,
    )


def resolve_stt_config(cfg: StreamingSTTConfig | None) -> StreamingSTTConfig | None:
    if not KENYA_PRODUCTION_MODE or cfg is None:
        return cfg
    return KENYA_PRODUCTION_STT_CONFIG


def resolve_llm_config(cfg: StreamingLLMConfig | None) -> StreamingLLMConfig | None:
    if not KENYA_PRODUCTION_MODE or cfg is None:
        return cfg
    return KENYA_PRODUCTION_LLM_CONFIG


def resolve_tts_config(cfg: StreamingTTSConfig | None) -> StreamingTTSConfig | None:
    if not KENYA_PRODUCTION_MODE or cfg is None:
        return cfg
    return replace(
        KENYA_PRODUCTION_TTS_CONFIG,
        elevenlabs_voice_id=cfg.elevenlabs_voice_id,
    )
