"""Tests for DTMF gather processor."""

from unittest.mock import AsyncMock

import pytest
from pipecat.audio.dtmf.types import KeypadEntry
from pipecat.frames.frames import InputDTMFFrame
from pipecat.processors.frame_processor import FrameDirection

from api.services.pipecat.dtmf_gather_processor import DtmfGatherProcessor


@pytest.mark.asyncio
async def test_dtmf_processor_invokes_callback():
    on_digit = AsyncMock()
    processor = DtmfGatherProcessor(on_digit=on_digit)
    processor.push_frame = AsyncMock()

    frame = InputDTMFFrame(button=KeypadEntry.ONE)
    await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

    on_digit.assert_awaited_once_with("1")
    processor.push_frame.assert_awaited_once_with(frame, FrameDirection.DOWNSTREAM)
