"""Pipecat frame processor: STT → LLM → TTS → tool latency without blocking audio."""

from __future__ import annotations

import time

from pipecat.frames.frames import (
    Frame,
    FunctionCallInProgressFrame,
    FunctionCallResultFrame,
    LLMFullResponseStartFrame,
    TranscriptionFrame,
    TTSStartedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from api.services.realtime_observability.metrics import (
    LLM_FIRST_TOKEN_MS,
    STT_RESPONSE_MS,
    TOOL_CALL_MS,
    TTS_FIRST_BYTE_MS,
)
from api.services.realtime_observability.percentiles import record_stage_ms


class TurnLatencyProcessor(FrameProcessor):
    """Observes classic Pipecat frames and records stage histograms."""

    def __init__(self):
        super().__init__()
        self._turn_start: float | None = None
        self._tool_start: float | None = None
        self._marked_llm = False
        self._marked_tts = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, TranscriptionFrame) and getattr(frame, "text", None):
                now = time.monotonic()
                if self._turn_start is not None:
                    ms = (now - self._turn_start) * 1000.0
                    STT_RESPONSE_MS.observe(ms)
                    record_stage_ms("stt", ms)
                self._turn_start = now
                self._marked_llm = False
                self._marked_tts = False
            elif isinstance(frame, LLMFullResponseStartFrame) and self._turn_start:
                if not self._marked_llm:
                    ms = (time.monotonic() - self._turn_start) * 1000.0
                    LLM_FIRST_TOKEN_MS.observe(ms)
                    record_stage_ms("llm_first_token", ms)
                    self._marked_llm = True
            elif isinstance(frame, TTSStartedFrame) and self._turn_start:
                if not self._marked_tts:
                    ms = (time.monotonic() - self._turn_start) * 1000.0
                    TTS_FIRST_BYTE_MS.observe(ms)
                    record_stage_ms("tts_first_byte", ms)
                    self._marked_tts = True
            elif isinstance(frame, FunctionCallInProgressFrame):
                self._tool_start = time.monotonic()
            elif isinstance(frame, FunctionCallResultFrame) and self._tool_start:
                ms = (time.monotonic() - self._tool_start) * 1000.0
                TOOL_CALL_MS.observe(ms)
                record_stage_ms("tool_call", ms)
                self._tool_start = None

        await self.push_frame(frame, direction)
