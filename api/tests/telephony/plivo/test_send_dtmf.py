"""Tests for Plivo outbound DTMF."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.telephony.providers.plivo.provider import PlivoProvider


def _provider() -> PlivoProvider:
    return PlivoProvider(
        {
            "auth_id": "MA_TEST",
            "auth_token": "token",
            "from_numbers": ["+254711082000"],
        }
    )


@pytest.mark.asyncio
async def test_plivo_send_dtmf_calls_api():
    provider = _provider()

    class FakeResponse:
        status = 202

        async def text(self):
            return ""

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
        result = await provider.send_dtmf("call-uuid-1", "12#")

    assert result["status"] == "sent"
    assert result["digits"] == "12#"
    assert provider.supports_dtmf() is True
