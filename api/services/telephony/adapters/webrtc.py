"""WebRTC / web-call adapter.

Browser calls never go through a PSTN carrier. START_CALL with
``CallTransport.WEBRTC`` returns a session the signaling layer already
knows how to complete. Provider-specific SDP/ICE stays in the WebRTC
signaling routes.
"""

from __future__ import annotations

from api.services.telephony.domain import CallCommand, CallTransport, PhoneNumber, VoiceCall
from api.services.telephony.start_call import StartCallRequest, StartCallResult


async def start_webrtc_call(request: StartCallRequest) -> StartCallResult:
    phone = PhoneNumber(e164=request.to_number, original=request.to_number)
    return StartCallResult(
        call=VoiceCall(
            workflow_run_id=request.workflow_run_id,
            organization_id=request.organization_id,
            to=phone,
            command=CallCommand.START_CALL,
            transport=CallTransport.WEBRTC,
            provider_name="webrtc",
            purpose=request.purpose,
        ),
        attempt_log=[{"provider": "webrtc", "status": "signaling"}],
    )
