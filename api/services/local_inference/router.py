"""Cluster-local inference endpoint routing for on-prem deployments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any

from loguru import logger

from api.constants import LOCAL_INFERENCE_ENABLED, LOCAL_INFERENCE_ROUTES_JSON


class InferenceService(str, Enum):
    LLM = "llm"
    STT = "stt"
    TTS = "tts"


@dataclass(frozen=True)
class InferenceEndpoint:
    service: InferenceService
    url: str
    provider: str
    default_model: str
    timeout_seconds: int = 60


class LocalInferenceRouter:
    """Resolve in-cluster LLM/STT/TTS endpoints from LOCAL_INFERENCE_ROUTES."""

    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self._routes = routes if routes is not None else _load_routes()

    @property
    def enabled(self) -> bool:
        return LOCAL_INFERENCE_ENABLED and bool(self._routes)

    def get(self, service: InferenceService) -> InferenceEndpoint | None:
        raw = self._routes.get(service.value)
        if not raw or not raw.get("url"):
            return None
        return InferenceEndpoint(
            service=service,
            url=str(raw["url"]),
            provider=str(raw.get("provider", "speaches")),
            default_model=str(raw.get("default_model", "")),
            timeout_seconds=int(raw.get("timeout_seconds", 60)),
        )

    def as_provider_defaults(self) -> dict[str, dict[str, str]]:
        """Suggested org-level AI config defaults for on-prem installs."""
        out: dict[str, dict[str, str]] = {}
        for service in InferenceService:
            endpoint = self.get(service)
            if endpoint is None:
                continue
            out[service.value] = {
                "provider": endpoint.provider,
                "base_url": endpoint.url,
                "model": endpoint.default_model,
            }
        return out

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "routing_mode": "cluster-local",
            "endpoints": {
                svc.value: (
                    {
                        "url": ep.url,
                        "provider": ep.provider,
                        "default_model": ep.default_model,
                    }
                    if (ep := self.get(svc))
                    else None
                )
                for svc in InferenceService
            },
        }


@lru_cache(maxsize=1)
def get_local_inference_router() -> LocalInferenceRouter:
    return LocalInferenceRouter()


def _load_routes() -> dict[str, Any]:
    if not LOCAL_INFERENCE_ROUTES_JSON:
        return {}
    try:
        data = json.loads(LOCAL_INFERENCE_ROUTES_JSON)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as e:
        logger.warning("Invalid LOCAL_INFERENCE_ROUTES JSON: {}", e)
    return {}
