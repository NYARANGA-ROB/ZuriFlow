"""Tests for Twilio outbound DTMF."""

from unittest.mock import patch

import pytest

from api.services.telephony.providers.twilio.provider import TwilioProvider


def _provider() -> TwilioProvider:
    return TwilioProvider(
        {
            "account_sid": "AC_TEST",
            "auth_token": "token",
            "from_numbers": ["+254711082000"],
        }
    )


@pytest.mark.asyncio
async def test_twilio_send_dtmf_calls_api():
    provider = _provider()

    class FakeResponse:
        status = 200

        async def text(self):
            return '{"sid": "CA123"}'

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
        result = await provider.send_dtmf("CA123", "1w2")

    assert result["status"] == "sent"
    assert result["digits"] == "1w2"
    assert provider.supports_dtmf() is True
