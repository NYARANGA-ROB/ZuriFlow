"""Tests for unified omnichannel engagement."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.omnichannel.consent import ConsentService
from api.services.omnichannel.followups import DEFAULT_RULES
from api.services.omnichannel.identity import CustomerIdentityService
from api.services.omnichannel.orchestrator import ChannelOrchestrator
from api.services.omnichannel.types import (
    Channel,
    FollowupTrigger,
    MessagePurpose,
    OrchestrationAction,
)


@pytest.mark.asyncio
async def test_identity_merges_phone_and_email_to_one_customer():
    service = CustomerIdentityService()
    with patch("api.services.omnichannel.identity.db_client") as db:
        db.get_customer = AsyncMock(return_value=None)
        db.get_identity = AsyncMock(
            side_effect=[
                SimpleNamespace(customer_id=4),
                SimpleNamespace(customer_id=9),
                None,
                None,
            ]
        )
        db.get_customer_by_phone = AsyncMock(return_value=SimpleNamespace(id=4))
        db.reassign_identities = AsyncMock(return_value=1)
        db.update_customer = AsyncMock()
        db.upsert_identity = AsyncMock()
        db.list_identities_for_customer = AsyncMock(
            return_value=[
                SimpleNamespace(kind="phone", value="+254712345678"),
                SimpleNamespace(kind="email", value="a@b.co.ke"),
            ]
        )
        match = await service.resolve(
            organization_id=1,
            phone="+254712345678",
            email="a@b.co.ke",
        )
    assert match.customer_id == 4
    assert 9 in match.merged_from
    db.reassign_identities.assert_awaited()


@pytest.mark.asyncio
async def test_consent_blocks_marketing_without_opt_in():
    prefs = SimpleNamespace(
        marketing_consent=False,
        transactional_consent=True,
        sms_opt_out=False,
        legal_basis="contract",
    )
    service = ConsentService()
    with patch.object(service, "get_or_create", AsyncMock(return_value=prefs)):
        decision = await service.decide(
            organization_id=1,
            customer_id=3,
            channel=Channel.SMS,
            purpose=MessagePurpose.MARKETING,
        )
    assert decision.allowed is False
    assert "marketing" in decision.reason


@pytest.mark.asyncio
async def test_consent_allows_transactional_sms():
    prefs = SimpleNamespace(
        marketing_consent=False,
        transactional_consent=True,
        sms_opt_out=False,
        legal_basis="contract",
    )
    service = ConsentService()
    with patch.object(service, "get_or_create", AsyncMock(return_value=prefs)):
        decision = await service.decide(
            organization_id=1,
            customer_id=3,
            channel=Channel.SMS,
            purpose=MessagePurpose.TRANSACTIONAL,
        )
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_orchestrator_keeps_voice_payment_and_sms_on_one_thread():
    identity = SimpleNamespace(customer_id=11)
    conversation = SimpleNamespace(id=22)
    message = SimpleNamespace(id=33)
    orchestrator = ChannelOrchestrator()
    conversations = MagicMock()
    conversations.get_or_open = AsyncMock(return_value=(identity, conversation))
    conversations.append = AsyncMock(return_value=message)
    consent = MagicMock()
    consent.decide = AsyncMock(
        return_value=SimpleNamespace(allowed=True, to_dict=lambda: {"allowed": True})
    )

    with (
        patch(
            "api.services.omnichannel.orchestrator.get_conversation_service",
            return_value=conversations,
        ),
        patch(
            "api.services.omnichannel.orchestrator.get_consent_service",
            return_value=consent,
        ),
    ):
        call = await orchestrator.execute(
            organization_id=1,
            action=OrchestrationAction.START_CALL,
            phone="+254700000000",
        )
        receipt = await orchestrator.execute(
            organization_id=1,
            action=OrchestrationAction.SEND_RECEIPT,
            phone="+254700000000",
            transaction_id=88,
            body="M-Pesa receipt KES 500",
        )
        sms = await orchestrator.execute(
            organization_id=1,
            action=OrchestrationAction.SEND_SMS,
            phone="+254700000000",
            body="Payment received. Asante.",
        )

    assert call["conversation_id"] == receipt["conversation_id"] == sms["conversation_id"] == 22
    assert sms["channel"] == "sms"
    assert conversations.get_or_open.await_count == 3


def test_default_followups_cover_kenya_journeys():
    triggers = {rule["trigger_event"] for rule in DEFAULT_RULES}
    assert FollowupTrigger.MISSED_CALL.value in triggers
    assert FollowupTrigger.PAYMENT_SUCCESS.value in triggers
    assert FollowupTrigger.APPOINTMENT_BOOKED.value in triggers
    assert FollowupTrigger.HUMAN_REQUESTED.value in triggers
