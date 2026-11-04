"""Tests for telephony IVR processor."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pipecat.utils.text.pattern_pair_aggregator import PatternMatch

from api.services.pipecat.telephony_ivr_processor import TelephonyIvrProcessor


@pytest.mark.asyncio
async def test_ivr_processor_sends_dtmf_via_callback():
    callback = AsyncMock()
    processor = TelephonyIvrProcessor(send_dtmf_callback=callback)
    processor.push_frame = AsyncMock()

    await processor._handle_dtmf_action(
        PatternMatch(content="2", type="dtmf", full_match="<dtmf>2</dtmf>")
    )

    callback.assert_awaited_once_with("2")
    processor.push_frame.assert_awaited()
