"""Tests for telephony failover org configuration helpers."""

from unittest.mock import AsyncMock, patch

import pytest

from api.services.telephony.failover import (
    get_failover_configuration,
    save_failover_configuration,
)


@pytest.mark.asyncio
async def test_get_failover_configuration_defaults():
    with patch(
        "api.services.telephony.failover.db_client.get_configuration",
        new=AsyncMock(return_value=None),
    ):
        data = await get_failover_configuration(1)
    assert data == {"enabled": False, "configuration_ids": []}


@pytest.mark.asyncio
async def test_save_failover_configuration_persists():
    upsert = AsyncMock()
    with patch(
        "api.services.telephony.failover.db_client.upsert_configuration",
        upsert,
    ):
        data = await save_failover_configuration(
            7, enabled=True, configuration_ids=[1, 2]
        )
    assert data["enabled"] is True
    assert data["configuration_ids"] == [1, 2]
    upsert.assert_awaited_once()
