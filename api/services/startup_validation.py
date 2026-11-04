"""Production startup validation — fail fast on unsafe configuration."""

from __future__ import annotations

from loguru import logger

from api.constants import AUTH_PROVIDER, DEPLOYMENT_MODE, ENVIRONMENT, LOCAL_INFERENCE_ENABLED, OSS_JWT_SECRET
from api.enums import Environment


_INSECURE_JWT_SECRETS = frozenset(
    {
        "",
        "change-me-in-production",
        "changeme",
        "secret",
        "dev",
    }
)


def validate_production_config() -> None:
    """Raise RuntimeError when mandatory production settings are missing or unsafe."""
    is_prod = ENVIRONMENT == Environment.PRODUCTION.value or DEPLOYMENT_MODE != "oss"
    if not is_prod:
        return

    if AUTH_PROVIDER == "local":
        if not OSS_JWT_SECRET or OSS_JWT_SECRET in _INSECURE_JWT_SECRETS:
            raise RuntimeError(
                "OSS_JWT_SECRET must be set to a strong random value in production "
                "(AUTH_PROVIDER=local)"
            )
        if len(OSS_JWT_SECRET) < 32:
            raise RuntimeError("OSS_JWT_SECRET must be at least 32 characters in production")

    if LOCAL_INFERENCE_ENABLED:
        from api.services.local_inference.router import get_local_inference_router

        router = get_local_inference_router()
        if not router.enabled:
            logger.warning(
                "LOCAL_INFERENCE_ENABLED is true but LOCAL_INFERENCE_ROUTES is empty"
            )
        else:
            logger.info("Local inference routing: {}", router.summary())

    logger.info("Production configuration validation passed")
