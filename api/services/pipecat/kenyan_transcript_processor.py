"""Apply Kenyan localization between STT and the workflow engine."""

from __future__ import annotations

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.utils.run_context import get_current_org_id

from api.services.kenya.pipeline import process_kenya_turn
from api.services.kenyan_telephony.integration import (
    kenyan_telephony_enabled,
    resolve_telephony_intent,
)


class KenyanTranscriptProcessor(FrameProcessor):
    """STT → Kenya layer → workflow. Original transcript is preserved on the frame."""

    def __init__(self, *, session_id: str = "telephony"):
        super().__init__()
        self._session_id = session_id

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if (
            kenyan_telephony_enabled()
            and direction == FrameDirection.DOWNSTREAM
            and isinstance(frame, TranscriptionFrame)
            and frame.text
        ):
            original = frame.text
            org = get_current_org_id()
            org_id = int(org) if org and str(org).isdigit() else None
            from api.services.realtime_observability.correlation import get_call_id

            turn = process_kenya_turn(
                original,
                session_id=self._session_id,
                organization_id=org_id,
            )
            setattr(frame, "original_transcript", turn.original_transcript)
            setattr(frame, "kenya_turn", turn.to_dict())
            call_id = get_call_id()
            if call_id:
                setattr(frame, "call_id", call_id)
            if turn.normalized_transcript:
                frame.text = turn.normalized_transcript
            resolve_telephony_intent(frame.text, session_id=self._session_id)

        await self.push_frame(frame, direction)
