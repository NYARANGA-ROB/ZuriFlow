"""Modular realtime voice pipeline.

This package introduces async-first, injectable services for telephony,
streaming, STT, LLM, TTS, and metrics. Production telephony calls continue
to run through ``LegacyVoiceOrchestrator`` (Pipecat bridge) while new code
can compose ``ModularVoiceOrchestrator`` or ``RealtimeVoiceOrchestrator``.
"""

from __future__ import annotations

from api.services.voice_pipeline.container import (
    VoicePipelineContainer,
    VoicePipelineDependencies,
    default_example_container,
    production_pipecat_container,
)
from api.services.voice_pipeline.orchestrator import (
    LegacyVoiceOrchestrator,
    ModularVoiceOrchestrator,
    build_config_from_context,
    run_voice_session,
)
from api.services.voice_pipeline.types import (
    AudioChunk,
    InboundCallContext,
    VoicePipelineConfig,
)

__all__ = [
    "AudioChunk",
    "InboundCallContext",
    "LegacyVoiceOrchestrator",
    "ModularVoiceOrchestrator",
    "RealtimeVoiceOrchestrator",
    "VoicePipelineConfig",
    "VoicePipelineContainer",
    "VoicePipelineDependencies",
    "build_config_from_context",
    "create_realtime_voice_orchestrator",
    "create_realtime_voice_orchestrator_from_env",
    "default_example_container",
    "production_pipecat_container",
    "run_voice_session",
]


def __getattr__(name: str):
    if name == "RealtimeVoiceOrchestrator":
        from api.services.realtime_voice_pipeline import RealtimeVoiceOrchestrator

        return RealtimeVoiceOrchestrator
    if name == "create_realtime_voice_orchestrator":
        from api.services.realtime_voice_pipeline import create_realtime_voice_orchestrator

        return create_realtime_voice_orchestrator
    if name == "create_realtime_voice_orchestrator_from_env":
        from api.services.realtime_voice_pipeline import (
            create_realtime_voice_orchestrator_from_env,
        )

        return create_realtime_voice_orchestrator_from_env
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
