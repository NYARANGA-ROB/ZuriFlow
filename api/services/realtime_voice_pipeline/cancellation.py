"""Backward-compatible alias for interruption cancellation."""

from api.services.realtime_voice_pipeline.interruption.cancellation import (
    InterruptionCancellationManager,
)

PipelineCancellationManager = InterruptionCancellationManager

__all__ = ["InterruptionCancellationManager", "PipelineCancellationManager"]
