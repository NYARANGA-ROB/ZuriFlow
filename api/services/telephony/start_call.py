"""Provider-independent START_CALL execution.

Workflows request START_CALL. Adapter selection stays inside the telephony
registry and failover layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from loguru import logger

from api.services.telephony.call_events import events_show_customer_on_line
from api.services.telephony.domain import (
    CallCommand,
    CallPurpose,
    CallTransport,
    PhoneNumber,
    VoiceCall,
)
from api.services.telephony.kenya_dialing import resolve_outbound_number
from api.services.telephony.start_call_policy import (
    StartCallPolicy,
    assert_start_call_allowed,
)

WebhookUrlFactory = Callable[[Any], str]


@dataclass
class StartCallRequest:
    organization_id: int
    workflow_run_id: int
    to_number: str
    webhook_url_for_provider: WebhookUrlFactory
    telephony_configuration_id: int | None = None
    from_number: str | None = None
    initiate_kwargs: dict[str, Any] | None = None
    purpose: CallPurpose = CallPurpose.TRANSACTIONAL
    transport: CallTransport = CallTransport.PSTN
    allow_failover: bool = True
    respect_business_hours: bool = False
    require_consent: bool = False
    customer_id: int | None = None
    campaign_id: int | None = None


@dataclass
class StartCallResult:
    call: VoiceCall
    attempt_log: list[dict[str, Any]]
    skipped_failover: bool = False
    provider: Any = None
    initiation_result: Any = None


async def execute_start_call(request: StartCallRequest) -> StartCallResult:
    if request.transport == CallTransport.WEBRTC:
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
                campaign_id=request.campaign_id,
            ),
            attempt_log=[{"provider": "webrtc", "status": "signaling"}],
        )

    phone = resolve_outbound_number(request.to_number)
    from_number = request.from_number
    if from_number:
        try:
            from_number = resolve_outbound_number(from_number).e164
        except ValueError:
            pass

    await assert_start_call_allowed(
        organization_id=request.organization_id,
        policy=StartCallPolicy(
            purpose=request.purpose,
            respect_business_hours=request.respect_business_hours,
            require_consent=request.require_consent,
            customer_id=request.customer_id,
            campaign_id=request.campaign_id,
        ),
    )

    allow_failover = request.allow_failover
    if allow_failover and request.workflow_run_id:
        allow_failover = not await _customer_already_on_line(request.workflow_run_id)

    from api.services.telephony.failover import initiate_call_with_failover

    provider, result, winning_id, attempt_log = await initiate_call_with_failover(
        request.organization_id,
        request.telephony_configuration_id,
        to_number=phone.e164,
        webhook_url_for_provider=request.webhook_url_for_provider,
        workflow_run_id=request.workflow_run_id,
        from_number=from_number,
        initiate_kwargs=request.initiate_kwargs,
        allow_failover=allow_failover,
    )

    call = VoiceCall(
        workflow_run_id=request.workflow_run_id,
        organization_id=request.organization_id,
        to=phone,
        command=CallCommand.START_CALL,
        from_number=result.caller_number or from_number,
        transport=CallTransport.PSTN,
        provider_name=provider.PROVIDER_NAME,
        provider_call_id=result.call_id,
        telephony_configuration_id=winning_id,
        campaign_id=request.campaign_id,
        purpose=request.purpose,
    )
    skipped = (not allow_failover) and request.allow_failover
    if skipped:
        logger.info(
            "START_CALL skipped carrier failover for customer-facing run {}",
            request.workflow_run_id,
        )
    return StartCallResult(
        call=call,
        attempt_log=attempt_log,
        skipped_failover=skipped,
        provider=provider,
        initiation_result=result,
    )


async def _customer_already_on_line(workflow_run_id: int) -> bool:
    from api.db import db_client

    run = await db_client.get_workflow_run_by_id(workflow_run_id)
    if not run:
        return False
    events = (run.logs or {}).get("call_events") or []
    return events_show_customer_on_line(events)
