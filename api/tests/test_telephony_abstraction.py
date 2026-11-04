"""Provider-independent telephony domain: START_CALL, events, Kenya dialing, quality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.telephony.call_events import (
    CallEventType,
    events_show_customer_on_line,
    is_customer_facing,
    normalize_call_status,
)
from api.services.telephony.call_quality import build_quality_report
from api.services.telephony.kenya_dialing import resolve_outbound_number
from api.services.telephony.start_call import StartCallRequest, execute_start_call
from api.services.telephony.domain import CallCommand, CallPurpose, CallTransport


def test_normalize_call_status_maps_providers():
    assert normalize_call_status("ringing") is CallEventType.CALL_RINGING
    assert normalize_call_status("in-progress") is CallEventType.CALL_ANSWERED
    assert normalize_call_status("completed") is CallEventType.CALL_ENDED
    assert normalize_call_status("busy") is CallEventType.CALL_FAILED
    assert normalize_call_status("dtmf") is CallEventType.DTMF_RECEIVED


def test_customer_facing_events_block_failover():
    assert is_customer_facing(CallEventType.CALL_ANSWERED)
    assert events_show_customer_on_line(
        [{"type": "CALL_STARTED"}, {"type": "CALL_ANSWERED"}]
    )
    assert not events_show_customer_on_line([{"type": "CALL_STARTED"}])


def test_resolve_outbound_number_kenyan_local():
    phone = resolve_outbound_number("0712345678")
    assert phone.e164 == "+254712345678"
    assert phone.country == "KE"


def test_resolve_outbound_number_rejects_bad_kenya():
    with pytest.raises(ValueError):
        resolve_outbound_number("07123")


def test_quality_report_aggregates_latency_and_failures():
    run = MagicMock()
    run.id = 9
    run.usage_info = {
        "stt_latency_ms": 120,
        "llm_latency_ms": 400,
        "tts_latency_ms": 80,
    }
    run.extra = {"call_quality": {"packet_loss": 0.02, "network_latency_ms": 40}}
    run.logs = {"call_events": [{"type": "CALL_FAILED", "raw_status": "failed"}]}
    run.gathered_context = {"provider": "africastalking"}
    run.initial_context = {}
    report = build_quality_report(run)
    assert report["packet_loss"] == 0.02
    assert report["call_failed"] is True
    assert report["latency_ms"]["stt"] == 120
    assert report["latency_ms"]["total_response"] == 600


@pytest.mark.asyncio
async def test_execute_start_call_webrtc_does_not_dial_pstn():
    result = await execute_start_call(
        StartCallRequest(
            organization_id=1,
            workflow_run_id=2,
            to_number="browser-session",
            webhook_url_for_provider=lambda p: "",
            transport=CallTransport.WEBRTC,
        )
    )
    assert result.call.command is CallCommand.START_CALL
    assert result.call.transport is CallTransport.WEBRTC
    assert result.call.provider_name == "webrtc"
    assert result.initiation_result is None


@pytest.mark.asyncio
async def test_execute_start_call_uses_failover_without_naming_provider():
    provider = MagicMock()
    provider.PROVIDER_NAME = "twilio"
    initiation = MagicMock()
    initiation.caller_number = "+254700000000"
    initiation.call_id = "CA123"

    with patch(
        "api.services.telephony.start_call.assert_start_call_allowed",
        new=AsyncMock(),
    ), patch(
        "api.services.telephony.start_call._customer_already_on_line",
        new=AsyncMock(return_value=False),
    ), patch(
        "api.services.telephony.failover.initiate_call_with_failover",
        new=AsyncMock(return_value=(provider, initiation, 44, [{"status": "success"}])),
    ):
        result = await execute_start_call(
            StartCallRequest(
                organization_id=3,
                workflow_run_id=8,
                to_number="0712345678",
                webhook_url_for_provider=lambda p: "https://example/twilio",
                purpose=CallPurpose.TEST,
            )
        )

    assert result.call.provider_name == "twilio"
    assert result.call.to.e164 == "+254712345678"
    assert result.call.provider_call_id == "CA123"


@pytest.mark.asyncio
async def test_failover_disabled_when_customer_already_on_line():
    provider = MagicMock()
    provider.PROVIDER_NAME = "africastalking"
    initiation = MagicMock(caller_number=None, call_id="AT1")
    failover = AsyncMock(return_value=(provider, initiation, 1, []))

    with patch(
        "api.services.telephony.start_call.assert_start_call_allowed",
        new=AsyncMock(),
    ), patch(
        "api.services.telephony.start_call._customer_already_on_line",
        new=AsyncMock(return_value=True),
    ), patch(
        "api.services.telephony.failover.initiate_call_with_failover",
        failover,
    ):
        await execute_start_call(
            StartCallRequest(
                organization_id=1,
                workflow_run_id=9,
                to_number="+254712345678",
                webhook_url_for_provider=lambda p: "https://example/at",
                allow_failover=True,
            )
        )

    assert failover.await_args.kwargs["allow_failover"] is False
