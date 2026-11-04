"""Production optimizations for Kenyan AI voice deployments."""

from api.services.kenya_production.bottleneck_audit import StageTimer, get_bottleneck_audit
from api.services.kenya_production.profile import (
    KENYA_PRODUCTION_PIPELINE_CONFIG,
    resolve_llm_config,
    resolve_pipeline_config,
    resolve_stt_config,
    resolve_tts_config,
)

__all__ = [
    "KENYA_PRODUCTION_PIPELINE_CONFIG",
    "StageTimer",
    "get_bottleneck_audit",
    "resolve_llm_config",
    "resolve_pipeline_config",
    "resolve_stt_config",
    "resolve_tts_config",
]
