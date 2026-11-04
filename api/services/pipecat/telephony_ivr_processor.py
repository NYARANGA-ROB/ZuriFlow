"""IVR navigation processor that sends DTMF via telephony REST APIs."""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

from loguru import logger
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.extensions.ivr.ivr_navigator import IVRProcessor
from pipecat.frames.frames import TextFrame
from pipecat.utils.text.pattern_pair_aggregator import PatternMatch

DEFAULT_CLASSIFIER_PROMPT = (
    "Classify whether the caller is speaking to a human or an automated IVR menu. "
    "Respond with <mode>conversation</mode> or <mode>ivr</mode>."
)

DEFAULT_IVR_PROMPT = (
    "You are navigating a phone IVR. Listen to the menu and respond with "
    "<dtmf>1</dtmf> style tags to press keys. Use <ivr>wait</ivr> while menus "
    "play. Use <ivr>completed</ivr> when connected to a human."
)


class TelephonyIvrProcessor(IVRProcessor):
    """Route LLM <dtmf> tags to provider REST DTMF instead of WebSocket frames."""

    def __init__(
        self,
        *,
        send_dtmf_callback: Callable[[str], Awaitable[None]],
        classifier_prompt: str = DEFAULT_CLASSIFIER_PROMPT,
        ivr_prompt: str = DEFAULT_IVR_PROMPT,
        ivr_vad_params: VADParams | None = None,
    ):
        super().__init__(
            classifier_prompt=classifier_prompt,
            ivr_prompt=ivr_prompt,
            ivr_vad_params=ivr_vad_params,
        )
        self._send_dtmf_callback = send_dtmf_callback

    async def _handle_dtmf_action(self, match: PatternMatch):
        value = match.text
        logger.info(f"IVR DTMF action: {value}")
        try:
            await self._send_dtmf_callback(value)
            text_frame = TextFrame(text=f"<dtmf>{value}</dtmf>")
            text_frame.skip_tts = True
            await self.push_frame(text_frame)
        except Exception as exc:
            logger.error(f"Failed to send IVR DTMF '{value}': {exc}")


def create_telephony_ivr_processor(
    engine,
    *,
    classifier_prompt: Optional[str] = None,
    ivr_prompt: Optional[str] = None,
) -> TelephonyIvrProcessor:
    from api.services.telephony.dtmf_outbound import send_outbound_dtmf

    async def _send_digit(digit: str) -> None:
        await send_outbound_dtmf(engine, digit)

    return TelephonyIvrProcessor(
        send_dtmf_callback=_send_digit,
        classifier_prompt=classifier_prompt or DEFAULT_CLASSIFIER_PROMPT,
        ivr_prompt=ivr_prompt or DEFAULT_IVR_PROMPT,
    )
