"""Capture inbound DTMF keypresses from telephony transports."""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

from loguru import logger
from pipecat.frames.frames import Frame, InputDTMFFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class DtmfGatherProcessor(FrameProcessor):
    """Forward keypad digits to the workflow engine gathered context."""

    def __init__(
        self,
        *,
        on_digit: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        super().__init__()
        self._on_digit = on_digit

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if (
            direction == FrameDirection.DOWNSTREAM
            and isinstance(frame, InputDTMFFrame)
            and self._on_digit is not None
        ):
            digit = frame.button.value
            logger.info(f"DTMF digit received: {digit}")
            await self._on_digit(digit)

        await self.push_frame(frame, direction)
