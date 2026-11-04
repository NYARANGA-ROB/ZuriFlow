"""Voice cost optimization for AI calls."""

from api.services.voice_cost_optimization.service import (
    VoiceCostOptimizationService,
    get_voice_cost_optimization_service,
)

__all__ = [
    "VoiceCostOptimizationService",
    "get_voice_cost_optimization_service",
]
