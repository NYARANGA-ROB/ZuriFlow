"""Outbound telephony carrier failover across multiple provider configurations."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from api.constants import TELEPHONY_FAILOVER_ENABLED
from api.db import db_client
from api.enums import OrganizationConfigurationKey
from api.services.telephony.base import CallInitiationResult, TelephonyProvider
from api.services.telephony.factory import get_telephony_provider_by_id

FAILOVER_CONFIG_KEY = OrganizationConfigurationKey.TELEPHONY_FAILOVER_CONFIGURATION.value


async def load_failover_configuration_ids(
    organization_id: int,
    primary_configuration_id: int | None,
) -> list[int]:
    """Return an ordered, de-duplicated list of telephony configuration ids to try."""
    chain: list[int] = []
    if primary_configuration_id is not None:
        chain.append(int(primary_configuration_id))

    if not TELEPHONY_FAILOVER_ENABLED:
        return chain

    row = await db_client.get_configuration(organization_id, FAILOVER_CONFIG_KEY)
    if not row or not row.value:
        return chain

    value = row.value
    if not value.get("enabled", True):
        return chain

    for raw_id in value.get("configuration_ids") or []:
        try:
            config_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if config_id not in chain:
            chain.append(config_id)
    return chain


async def initiate_call_with_failover(
    organization_id: int,
    primary_configuration_id: int | None,
    *,
    to_number: str,
    webhook_url_for_provider: Callable[[TelephonyProvider], str],
    workflow_run_id: Optional[int] = None,
    from_number: Optional[str] = None,
    initiate_kwargs: Optional[dict[str, Any]] = None,
    allow_failover: bool = True,
) -> tuple[TelephonyProvider, CallInitiationResult, int, list[dict[str, Any]]]:
    """Try outbound call initiation across a failover chain.

    ``webhook_url_for_provider`` is called for each candidate provider so the
    answer URL can use the correct provider-specific webhook path.

    Failover only runs for pre-answer origination failures. Once a customer
    is on the line, callers must pass ``allow_failover=False`` so we do not
    redial them on another carrier.

    Returns ``(provider, result, winning_configuration_id, attempt_log)``.
    Raises the last exception when every configuration fails.
    """
    config_ids = await load_failover_configuration_ids(
        organization_id, primary_configuration_id
    )
    if not allow_failover and primary_configuration_id is not None:
        config_ids = [int(primary_configuration_id)]
    if not config_ids:
        raise ValueError(
            f"No telephony configuration available for organization {organization_id}"
        )

    attempt_log: list[dict[str, Any]] = []
    last_error: Exception | None = None
    kwargs = dict(initiate_kwargs or {})

    for config_id in config_ids:
        provider = await get_telephony_provider_by_id(config_id, organization_id)
        if not provider.validate_config():
            attempt_log.append(
                {
                    "configuration_id": config_id,
                    "provider": provider.PROVIDER_NAME,
                    "status": "skipped",
                    "error": "invalid_configuration",
                }
            )
            continue

        try:
            webhook_url = webhook_url_for_provider(provider)
            result = await provider.initiate_call(
                to_number=to_number,
                webhook_url=webhook_url,
                workflow_run_id=workflow_run_id,
                from_number=from_number,
                **kwargs,
            )
            attempt_log.append(
                {
                    "configuration_id": config_id,
                    "provider": provider.PROVIDER_NAME,
                    "status": "success",
                    "call_id": result.call_id,
                }
            )
            if len(attempt_log) > 1:
                logger.warning(
                    f"Telephony failover succeeded on configuration {config_id} "
                    f"for org {organization_id} after {len(attempt_log) - 1} failure(s)"
                )
            return provider, result, config_id, attempt_log
        except Exception as exc:
            last_error = exc
            logger.warning(
                f"Telephony initiate_call failed for configuration {config_id} "
                f"(org {organization_id}): {exc}"
            )
            attempt_log.append(
                {
                    "configuration_id": config_id,
                    "provider": provider.PROVIDER_NAME,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    if last_error is not None:
        raise last_error
    raise ValueError("All telephony configurations in failover chain are invalid")


async def save_failover_configuration(
    organization_id: int,
    *,
    enabled: bool,
    configuration_ids: list[int],
) -> dict[str, Any]:
    value = {
        "enabled": enabled,
        "configuration_ids": configuration_ids,
    }
    await db_client.upsert_configuration(organization_id, FAILOVER_CONFIG_KEY, value)
    return value


async def get_failover_configuration(organization_id: int) -> dict[str, Any]:
    row = await db_client.get_configuration(organization_id, FAILOVER_CONFIG_KEY)
    if not row or not row.value:
        return {"enabled": False, "configuration_ids": []}
    value = dict(row.value)
    value.setdefault("enabled", False)
    value.setdefault("configuration_ids", [])
    return value
