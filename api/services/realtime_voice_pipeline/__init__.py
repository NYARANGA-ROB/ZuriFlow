from api.services.realtime_voice_pipeline.config import (
    DEFAULT_PIPELINE_CONFIG,
    LOW_LATENCY_PIPELINE_CONFIG,
    RealtimeVoicePipelineConfig,
)

__all__ = [
    "DEFAULT_PIPELINE_CONFIG",
    "LOW_LATENCY_PIPELINE_CONFIG",
    "ConversationRecoveryManager",
    "ControlEventHandler",
    "InboundAudioHandler",
    "InterruptionCancellationManager",
    "InterruptionDetector",
    "InterruptionEvent",
    "InterruptionHandler",
    "InterruptionSource",
    "LowLatencyInboundHandler",
    "LLMResponseHandler",
    "PipelineLatencyTracker",
    "PipelineCancellationManager",
    "PipelineControlEvent",
    "PipelineControlKind",
    "PipelineEvent",
    "PipelineQueues",
    "PipelineStage",
    "RealtimeAudioMediaTransport",
    "RealtimeVoiceOrchestrator",
    "RealtimeVoicePipelineConfig",
    "RealtimeVoicePipelineDependencies",
    "RealtimeVoicePipelineManager",
    "STTAudioHandler",
    "STTRelayHandler",
    "TTSStopHandler",
    "TranscriptEventHandler",
    "VADConfig",
    "VADEvent",
    "VADEventKind",
    "VoiceActivityDetector",
    "create_realtime_voice_orchestrator",
    "create_realtime_voice_orchestrator_from_env",
    "run_realtime_voice_pipeline",
]


def __getattr__(name: str):
    if name == "PipelineCancellationManager":
        from api.services.realtime_voice_pipeline.cancellation import (
            PipelineCancellationManager,
        )

        return PipelineCancellationManager
    if name in ("create_realtime_voice_orchestrator", "create_realtime_voice_orchestrator_from_env"):
        from api.services.realtime_voice_pipeline import factory

        return getattr(factory, name)
    if name in (
        "ControlEventHandler",
        "InboundAudioHandler",
        "InterruptionHandler",
        "LLMResponseHandler",
        "LowLatencyInboundHandler",
        "STTAudioHandler",
        "STTRelayHandler",
        "TranscriptEventHandler",
    ):
        from api.services.realtime_voice_pipeline import handlers

        return getattr(handlers, name)
    if name == "PipelineLatencyTracker":
        from api.services.realtime_voice_pipeline.latency import PipelineLatencyTracker

        return PipelineLatencyTracker
    if name in (
        "ConversationRecoveryManager",
        "InterruptionCancellationManager",
        "InterruptionDetector",
        "InterruptionEvent",
        "InterruptionSource",
        "TTSStopHandler",
        "VADConfig",
        "VADEvent",
        "VADEventKind",
        "VoiceActivityDetector",
    ):
        from api.services.realtime_voice_pipeline import interruption

        return getattr(interruption, name)
    if name in ("RealtimeVoicePipelineDependencies", "RealtimeVoicePipelineManager"):
        from api.services.realtime_voice_pipeline import manager

        return getattr(manager, name)
    if name in ("RealtimeVoiceOrchestrator", "run_realtime_voice_pipeline"):
        from api.services.realtime_voice_pipeline import orchestrator

        return getattr(orchestrator, name)
    if name == "PipelineQueues":
        from api.services.realtime_voice_pipeline.queues import PipelineQueues

        return PipelineQueues
    if name == "RealtimeAudioMediaTransport":
        from api.services.realtime_voice_pipeline.transport import RealtimeAudioMediaTransport

        return RealtimeAudioMediaTransport
    if name in (
        "PipelineControlEvent",
        "PipelineControlKind",
        "PipelineEvent",
        "PipelineStage",
    ):
        from api.services.realtime_voice_pipeline import types

        return getattr(types, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
