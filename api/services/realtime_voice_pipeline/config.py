"""Configuration for the end-to-end realtime voice pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RealtimeVoicePipelineConfig:
    """Runtime settings for one streaming voice session."""

    session_id: str
    sample_rate: int = 16000
    channels: int = 1
    system_prompt: str = "You are a helpful voice assistant."

    # Low-latency mode — collapses queue hops and uses direct outbound.
    low_latency_mode: bool = True

    # Queues (tight bounds for <800ms target; drop rather than buffer)
    inbound_audio_maxsize: int = 8
    transcript_maxsize: int = 16
    llm_event_maxsize: int = 32
    outbound_audio_maxsize: int = 4
    control_maxsize: int = 8
    vad_events_maxsize: int = 8
    queue_put_timeout_s: float = 0.0  # 0 = put_nowait only on hot path

    # Interruption
    barge_in_on_speech_start: bool = True
    barge_in_on_partial: bool = True
    barge_in_on_vad: bool = True
    min_partial_chars_for_barge_in: int = 3
    interrupt_cooldown_s: float = 0.25

    # VAD
    vad_energy_threshold: float = 450.0
    vad_min_speech_frames: int = 2
    vad_hangover_frames: int = 4
    vad_frame_ms: float = 20.0
    inline_vad: bool = True  # skip vad_events queue when True

    # Streaming / TTS
    flush_tts_on_token: bool = True
    min_tts_push_chars: int = 1
    direct_outbound: bool = True
    parallel_service_start: bool = True
    prefetch_tts_on_turn: bool = True

    # Latency budget (ms) — used for metrics alerting
    target_e2e_latency_ms: int = 800

    # Kenyan conversational behavior (optional)
    kenyan_conversation_enabled: bool = False
    kenyan_domain: str = "general"

    # Realtime conversation memory
    realtime_memory_enabled: bool = False

    # Kenyan realtime business intent detection
    kenyan_intent_enabled: bool = False

    # Intent-driven call routing
    call_routing_enabled: bool = False

    # Voice-driven M-Pesa payments
    voice_mpesa_enabled: bool = False
    organization_id: int = 0
    phone_e164: str = ""
    customer_name: str = "there"
    payment_amount: float | None = None
    payment_language: str = "mixed"


DEFAULT_PIPELINE_CONFIG = RealtimeVoicePipelineConfig(session_id="")


LOW_LATENCY_PIPELINE_CONFIG = RealtimeVoicePipelineConfig(
    session_id="",
    low_latency_mode=True,
    inbound_audio_maxsize=4,
    transcript_maxsize=8,
    outbound_audio_maxsize=2,
    vad_hangover_frames=3,
    inline_vad=True,
    direct_outbound=True,
    parallel_service_start=True,
    prefetch_tts_on_turn=True,
    target_e2e_latency_ms=800,
)
