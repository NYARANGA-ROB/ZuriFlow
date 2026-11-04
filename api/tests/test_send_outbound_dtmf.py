"""Integration-style tests for outbound DTMF helper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.telephony.dtmf_outbound import send_outbound_dtmf


@pytest.mark.asyncio
async def test_send_outbound_dtmf_delegates_to_provider():
    engine = MagicMock()
    engine._workflow_run_id = 99
    engine._gathered_context = {}

    workflow_run = MagicMock()
    workflow_run.workflow_id = 1
    workflow_run.gathered_context = {"call_id": "call-123"}

    workflow = MagicMock()
    workflow.organization_id = 7

    provider = MagicMock()
    provider.PROVIDER_NAME = "twilio"
    provider.supports_dtmf.return_value = True
    provider.send_dtmf = AsyncMock(return_value={"status": "sent"})

    with patch(
        "api.services.telephony.dtmf_outbound.db_client.get_workflow_run_by_id",
        new=AsyncMock(return_value=workflow_run),
    ):
        with patch(
            "api.services.telephony.dtmf_outbound.db_client.get_workflow_by_id",
            new=AsyncMock(return_value=workflow),
        ):
            with patch(
                "api.services.telephony.factory.get_telephony_provider_for_run",
                new=AsyncMock(return_value=provider),
            ):
                result = await send_outbound_dtmf(engine, "1")

    assert result["status"] == "sent"
    provider.send_dtmf.assert_awaited_once_with("call-123", "1")
    assert engine._gathered_context["dtmf_sent"] == "1"
