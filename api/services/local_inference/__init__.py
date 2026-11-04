"""Local GPU inference routing for on-prem deployments."""

from api.services.local_inference.router import (
    InferenceEndpoint,
    InferenceService,
    LocalInferenceRouter,
    get_local_inference_router,
)

__all__ = [
    "InferenceEndpoint",
    "InferenceService",
    "LocalInferenceRouter",
    "get_local_inference_router",
]
