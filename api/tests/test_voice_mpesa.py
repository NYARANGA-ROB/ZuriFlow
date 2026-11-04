"""Tests for voice-driven M-Pesa payment workflow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.services.voice_mpesa.confirmation import VoicePaymentConfirmation
from api.services.voice_mpesa.engine import VoiceMpesaWorkflowEngine
from api.services.voice_mpesa.state_machine import VoicePaymentStateMachine
from api.services.voice_mpesa.types import VoicePaymentEvent, VoicePaymentState


def test_consent_detection():
    confirm = VoicePaymentConfirmation()
    assert confirm.is_consent("yes please lipa")
    assert confirm.is_decline("hapana not now")
    assert confirm.wants_retry("jaribu tena")


def test_state_machine_consent_flow():
    sm = VoicePaymentStateMachine()
    state = VoicePaymentState.IDLE
    state = sm.transition(state, VoicePaymentEvent.OFFER)
    assert state == VoicePaymentState.OFFERED
    state = sm.transition(state, VoicePaymentEvent.ASK_CONSENT)
    assert state == VoicePaymentState.AWAITING_CONSENT
    state = sm.transition(state, VoicePaymentEvent.CONSENT)
    assert state == VoicePaymentState.CONSENTED


def test_success_prompt_multilingual():
    confirm = VoicePaymentConfirmation()
    en = confirm.success_prompt(amount=500, currency="KES", receipt="ABC123", language="en")
    sw = confirm.success_prompt(amount=500, currency="KES", receipt="ABC123", language="sw")
    assert "ABC123" in en
    assert "ABC123" in sw
    assert "Malipo" in sw


@pytest.mark.asyncio
async def test_on_user_utterance_consent_triggers_stk():
    engine = VoiceMpesaWorkflowEngine()

    mock_response = AsyncMock(
        return_value=type(
            "R",
            (),
            {
                "success": True,
                "transaction_id": 99,
                "merchant_request_id": "m1",
                "checkout_request_id": "c1",
                "raw_response": {},
                "error": None,
            },
        )()
    )

    with (
        patch.object(engine, "_voice_config", AsyncMock()) as cfg_mock,
        patch.object(engine._stk, "initiate_stk_push", mock_response),
        patch.object(engine, "_persist_session", AsyncMock()),
        patch.object(engine, "_log_event", AsyncMock()),
        patch.object(engine, "_start_watcher"),
    ):
        cfg_mock.return_value = type("C", (), {"max_retries": 3})()
        session = await engine.ensure_session(
            session_id="sess-1",
            organization_id=1,
            workflow_run_id=10,
            phone_e164="+254712345678",
            customer_name="Jane",
            amount=100.0,
        )
        session.state = VoicePaymentState.AWAITING_CONSENT
        result = await engine.on_user_utterance("sess-1", "yes ndio")

    assert result.handled is True
    assert result.skip_llm_turn is True
    assert result.speak_prompt is not None
    assert session.transaction_id == 99


@pytest.mark.asyncio
async def test_decline_payment():
    engine = VoiceMpesaWorkflowEngine()

    with (
        patch.object(engine, "_voice_config", AsyncMock()) as cfg_mock,
        patch.object(engine, "_persist_session", AsyncMock()),
        patch.object(engine, "_log_event", AsyncMock()),
    ):
        cfg_mock.return_value = type("C", (), {"default_amount": 50.0, "max_retries": 3})()
        await engine.ensure_session(
            session_id="sess-2",
            organization_id=1,
            workflow_run_id=11,
            phone_e164="+254700000001",
            amount=50.0,
        )
        session = engine.get_session("sess-2")
        assert session is not None
        session.state = VoicePaymentState.AWAITING_CONSENT

        result = await engine.on_user_utterance("sess-2", "hapana not now")

    assert result.handled is True
    assert session.state == VoicePaymentState.DECLINED
