"""Tests for Africa's Talking telephony provider."""

from unittest.mock import AsyncMock, patch

import pytest

from api.services.telephony.providers.africastalking.provider import AfricasTalkingProvider


def _provider() -> AfricasTalkingProvider:
    return AfricasTalkingProvider(
        {
            "username": "sandbox",
            "api_key": "test-api-key",
            "from_numbers": ["+254711082000"],
        }
    )


def test_can_handle_webhook():
    assert AfricasTalkingProvider.can_handle_webhook(
        {
            "sessionId": "ATVId_123",
            "callerNumber": "+254700000001",
            "destinationNumber": "+254711082000",
        },
        {},
    )


def test_parse_inbound_webhook():
    data = AfricasTalkingProvider.parse_inbound_webhook(
        {
            "sessionId": "ATVId_123",
            "callerNumber": "+254700000001",
            "destinationNumber": "+254711082000",
            "callSessionState": "Ringing",
            "username": "sandbox",
        }
    )
    assert data.call_id == "ATVId_123"
    assert data.from_number == "+254700000001"
    assert data.to_number == "+254711082000"
    assert data.account_id == "sandbox"


@pytest.mark.asyncio
async def test_get_webhook_response_contains_stream():
    provider = _provider()
    with patch(
        "api.services.telephony.providers.africastalking.provider.build_telephony_websocket_url_for_run",
        new=AsyncMock(
            return_value="wss://api.example.com/api/v1/telephony/ws/1/2/3"
        ),
    ):
        xml = await provider.get_webhook_response(1, 2, 3)
    assert "<Stream" in xml
    assert "wss://api.example.com/api/v1/telephony/ws/1/2/3" in xml


@pytest.mark.asyncio
async def test_initiate_call_parses_session_id():
    provider = _provider()
    response_payload = {
        "entries": [
            {
                "phoneNumber": "+254700000002",
                "sessionId": "ATVId_abc",
                "status": "Queued",
            }
        ]
    }

    class FakeResponse:
        status = 200

        async def text(self):
            import json

            return json.dumps(response_payload)

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def post(self, *args, **kwargs):
            class PostCtx:
                async def __aenter__(self_inner):
                    return FakeResponse()

                async def __aexit__(self_inner, *args):
                    return None

            return PostCtx()

    with patch("aiohttp.ClientSession", return_value=FakeSession()):
        result = await provider.initiate_call(
            to_number="+254700000002",
            webhook_url="https://api.example.com/africastalking-xml",
            workflow_run_id=99,
        )

    assert result.call_id == "ATVId_abc"
    assert result.status == "Queued"
