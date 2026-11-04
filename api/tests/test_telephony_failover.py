"""Tests for telephony carrier failover."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.telephony.base import CallInitiationResult
from api.services.telephony.failover import (
    initiate_call_with_failover,
    load_failover_configuration_ids,
)


@pytest.mark.asyncio
async def test_load_failover_configuration_ids_primary_only():
    with patch(
        "api.services.telephony.failover.db_client.get_configuration",
        new=AsyncMock(return_value=None),
    ):
        ids = await load_failover_configuration_ids(1, 42)
    assert ids == [42]


@pytest.mark.asyncio
async def test_load_failover_configuration_ids_merges_chain():
    config_row = MagicMock()
    config_row.value = {"enabled": True, "configuration_ids": [5, 42, 5]}

    with patch(
        "api.services.telephony.failover.db_client.get_configuration",
        new=AsyncMock(return_value=config_row),
    ):
        ids = await load_failover_configuration_ids(1, 42)
    assert ids == [42, 5]


@pytest.mark.asyncio
async def test_initiate_call_with_failover_tries_next_provider():
    primary = MagicMock()
    primary.PROVIDER_NAME = "twilio"
    primary.validate_config.return_value = True
    primary.initiate_call = AsyncMock(side_effect=RuntimeError("primary down"))

    backup = MagicMock()
    backup.PROVIDER_NAME = "plivo"
    backup.validate_config.return_value = True
    backup.initiate_call = AsyncMock(
        return_value=CallInitiationResult(
            call_id="call-2",
            status="queued",
            caller_number="+15551230001",
            provider_metadata={"call_id": "call-2"},
            raw_response={},
        )
    )

    async def _provider_by_id(config_id, organization_id):
        return primary if config_id == 1 else backup

    with patch(
        "api.services.telephony.failover.load_failover_configuration_ids",
        new=AsyncMock(return_value=[1, 2]),
    ):
        with patch(
            "api.services.telephony.failover.get_telephony_provider_by_id",
            side_effect=_provider_by_id,
        ):
            provider, result, winning_id, attempts = await initiate_call_with_failover(
                99,
                1,
                to_number="+15551230002",
                webhook_url_for_provider=lambda p: f"https://example.com/{p.PROVIDER_NAME}",
            )

    assert winning_id == 2
    assert provider is backup
    assert result.call_id == "call-2"
    assert attempts[0]["status"] == "failed"
    assert attempts[1]["status"] == "success"
