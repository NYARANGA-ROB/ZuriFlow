"""Factory for streaming voice pipeline dependencies."""

from __future__ import annotations

import os
from dataclasses import replace

from api.services.realtime_audio.connection_manager import AudioSession
from api.services.realtime_voice_pipeline.config import (
    LOW_LATENCY_PIPELINE_CONFIG,
    RealtimeVoicePipelineConfig,
)
from api.services.realtime_voice_pipeline.low_latency_profiles import (
    LOW_LATENCY_LLM_CONFIG,
    LOW_LATENCY_STT_CONFIG,
    LOW_LATENCY_TTS_CONFIG,
)
from api.services.realtime_voice_pipeline.manager import RealtimeVoicePipelineDependencies
from api.services.realtime_voice_pipeline.orchestrator import RealtimeVoiceOrchestrator
from api.services.realtime_voice_pipeline.transport import RealtimeAudioMediaTransport
from api.services.streaming_llm.factory import create_streaming_llm_bridge
from api.services.streaming_stt.factory import create_streaming_stt_bridge
from api.services.streaming_tts.factory import create_streaming_tts_bridge
from api.constants import (
    CALL_ROUTING_ENABLED,
    KENYAN_CONVERSATION_ENABLED,
    KENYAN_INTENT_ENABLED,
    KENYA_PRODUCTION_MODE,
    REALTIME_MEMORY_ENABLED,
    VOICE_MPESA_ENABLED,
)
from api.services.kenya_production.profile import (
    resolve_llm_config,
    resolve_pipeline_config,
    resolve_stt_config,
    resolve_tts_config,
)
from api.services.kenyan_conversation.integration import merge_system_prompt
from api.services.call_routing.integration import call_routing_enabled_for_session
from api.services.kenyan_intent.integration import kenyan_intent_enabled_for_session
from api.services.realtime_observability.collector import VoiceObservabilityCollector
from api.services.voice_mpesa.integration import voice_mpesa_enabled_for_session


def create_realtime_voice_orchestrator(
    session: AudioSession,
    *,
    deepgram_api_key: str,
    whisper_api_key: str,
    openai_api_key: str,
    elevenlabs_api_key: str,
    elevenlabs_voice_id: str,
    system_prompt: str = "You are a helpful voice assistant.",
    workflow_run_id: int = 0,
    openai_model: str | None = None,
    low_latency: bool = True,
    pipeline_config: RealtimeVoicePipelineConfig | None = None,
) -> RealtimeVoiceOrchestrator:
    """Wire streaming STT, LLM, and TTS bridges for one WebSocket audio session."""
    kenyan_enabled = KENYAN_CONVERSATION_ENABLED
    memory_enabled = REALTIME_MEMORY_ENABLED
    meta = session.metadata or {}
    meta_domain = meta.get("kenyan_domain", "general")
    voice_mpesa = voice_mpesa_enabled_for_session(meta) and VOICE_MPESA_ENABLED
    kenyan_intent = kenyan_intent_enabled_for_session(meta) and KENYAN_INTENT_ENABLED
    call_routing = call_routing_enabled_for_session(meta) and CALL_ROUTING_ENABLED
    payment_amount = meta.get("payment_amount")
    if payment_amount is not None:
        try:
            payment_amount = float(payment_amount)
        except (TypeError, ValueError):
            payment_amount = None
    voice_fields = {
        "kenyan_intent_enabled": kenyan_intent,
        "call_routing_enabled": call_routing,
        "voice_mpesa_enabled": voice_mpesa,
        "organization_id": int(meta.get("organization_id", 0)),
        "phone_e164": str(meta.get("phone_e164") or meta.get("to_number") or ""),
        "customer_name": str(meta.get("customer_name", "there")),
        "payment_amount": payment_amount,
        "payment_language": str(meta.get("payment_language", "mixed")),
    }
    effective_prompt = system_prompt
    if kenyan_enabled:
        effective_prompt = merge_system_prompt(
            system_prompt,
            domain=meta_domain,
            language_mode=meta.get("kenyan_language_mode", "mixed"),
        )

    base_cfg = pipeline_config or (
        resolve_pipeline_config(
            replace(
                LOW_LATENCY_PIPELINE_CONFIG,
                session_id=session.session_id,
                sample_rate=session.sample_rate,
                channels=session.channels,
                system_prompt=effective_prompt,
                kenyan_conversation_enabled=kenyan_enabled,
                kenyan_domain=meta_domain,
                realtime_memory_enabled=memory_enabled,
                **voice_fields,
            )
        )
        if low_latency
        else RealtimeVoicePipelineConfig(
            session_id=session.session_id,
            sample_rate=session.sample_rate,
            channels=session.channels,
            system_prompt=effective_prompt,
            low_latency_mode=False,
            direct_outbound=False,
            kenyan_conversation_enabled=kenyan_enabled,
            kenyan_domain=meta_domain,
            realtime_memory_enabled=memory_enabled,
            **voice_fields,
        )
    )
    transport = RealtimeAudioMediaTransport(session)

    stt_cfg = resolve_stt_config(LOW_LATENCY_STT_CONFIG if low_latency else None)
    llm_cfg = resolve_llm_config(LOW_LATENCY_LLM_CONFIG if low_latency else None)
    tts_cfg = resolve_tts_config(
        replace(LOW_LATENCY_TTS_CONFIG, elevenlabs_voice_id=elevenlabs_voice_id)
        if low_latency
        else None
    )

    stt = create_streaming_stt_bridge(
        deepgram_api_key=deepgram_api_key,
        whisper_api_key=whisper_api_key,
        config=stt_cfg,
    )
    llm = create_streaming_llm_bridge(
        api_key=openai_api_key, model=openai_model, config=llm_cfg
    )
    tts = create_streaming_tts_bridge(
        api_key=elevenlabs_api_key,
        voice_id=elevenlabs_voice_id,
        config=tts_cfg,
    )

    deps = RealtimeVoicePipelineDependencies(
        config=base_cfg,
        transport=transport,
        stt=stt,
        llm=llm,
        tts=tts,
        metrics=VoiceObservabilityCollector(
            workflow_run_id or 0,
            endpoint="realtime_voice",
            session_id=session.session_id,
        ),
        workflow_run_id=workflow_run_id,
    )
    return RealtimeVoiceOrchestrator(deps)


def create_realtime_voice_orchestrator_from_env(
    session: AudioSession,
    *,
    system_prompt: str = "You are a helpful voice assistant.",
    workflow_run_id: int = 0,
    elevenlabs_voice_id: str | None = None,
    low_latency: bool = True,
) -> RealtimeVoiceOrchestrator:
    """Build orchestrator using API keys from environment variables."""
    voice_id = elevenlabs_voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")
    if not voice_id:
        raise ValueError("ELEVENLABS_VOICE_ID is required")

    return create_realtime_voice_orchestrator(
        session,
        deepgram_api_key=os.environ["DEEPGRAM_API_KEY"],
        whisper_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_api_key=os.environ["OPENAI_API_KEY"],
        elevenlabs_api_key=os.environ["ELEVENLABS_API_KEY"],
        elevenlabs_voice_id=voice_id,
        system_prompt=system_prompt,
        workflow_run_id=workflow_run_id,
        low_latency=low_latency,
    )
