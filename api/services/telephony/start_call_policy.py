"""Policy gates for outbound START_CALL: hours, consent, campaign cancellation."""

from __future__ import annotations

from dataclasses import dataclass

from api.db import db_client
from api.services.kenya.hours import is_within_business_hours
from api.services.omnichannel.consent import get_consent_service
from api.services.omnichannel.types import Channel, MessagePurpose
from api.services.telephony.domain import CallPurpose


class StartCallRejected(Exception):
    def __init__(self, reason: str, *, http_status: int = 400):
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


@dataclass(frozen=True)
class StartCallPolicy:
    purpose: CallPurpose = CallPurpose.TRANSACTIONAL
    respect_business_hours: bool = False
    require_consent: bool = False
    customer_id: int | None = None
    campaign_id: int | None = None


async def assert_start_call_allowed(
    *,
    organization_id: int,
    policy: StartCallPolicy,
) -> None:
    if policy.campaign_id is not None:
        campaign = await db_client.get_campaign_by_id(policy.campaign_id)
        if not campaign or campaign.organization_id != organization_id:
            raise StartCallRejected("campaign_not_found", http_status=404)
        if campaign.state in {"cancelled", "failed", "completed", "paused"}:
            raise StartCallRejected(f"campaign_{campaign.state}", http_status=409)

    if policy.respect_business_hours and not is_within_business_hours():
        raise StartCallRejected("outside_business_hours", http_status=422)

    if policy.require_consent or policy.purpose == CallPurpose.MARKETING:
        if policy.customer_id is None:
            raise StartCallRejected("consent_requires_customer", http_status=403)
        decision = await get_consent_service().decide(
            organization_id=organization_id,
            customer_id=policy.customer_id,
            channel=Channel.VOICE,
            purpose=MessagePurpose.MARKETING
            if policy.purpose == CallPurpose.MARKETING
            else MessagePurpose.TRANSACTIONAL,
        )
        if not decision.allowed:
            raise StartCallRejected(decision.reason, http_status=403)
