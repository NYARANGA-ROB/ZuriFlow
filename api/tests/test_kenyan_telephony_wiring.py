"""Tests for Kenyan telephony pipeline wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from api.services.kenya.config import KenyaLanguage
from api.services.kenya.entities import ExtractedEntities
from api.services.kenya.language import ConversationalMix, DetectedStyle, LanguageGuess
from api.services.kenya.pipeline import KenyaTurn
from api.services.kenyan_telephony.integration import normalize_telephony_transcript
from api.services.pipecat.kenyan_transcript_processor import KenyanTranscriptProcessor


def test_normalize_telephony_transcript_disabled(monkeypatch):
    monkeypatch.setattr(
        "api.services.kenyan_telephony.integration.KENYAN_NORMALIZE_ENABLED", False
    )
    monkeypatch.setattr(
        "api.services.kenyan_telephony.integration.KENYAN_CONVERSATION_ENABLED", False
    )
    assert normalize_telephony_transcript("nataka balance") == "nataka balance"


def test_normalize_telephony_transcript_uses_behavior(monkeypatch):
    monkeypatch.setattr(
        "api.services.kenyan_telephony.integration.KENYAN_CONVERSATION_ENABLED", True
    )
    behavior = MagicMock()
    behavior.enabled = True
    behavior.normalize_caller_text.return_value = "I want my balance"
    with patch(
        "api.services.kenyan_conversation.integration.get_kenyan_conversation_behavior",
        return_value=behavior,
    ):
        out = normalize_telephony_transcript("nataka balance yangu")
    assert out == "I want my balance"


@pytest.mark.asyncio
async def test_kenyan_transcript_processor_normalizes_final_frame(monkeypatch):
    monkeypatch.setattr(
        "api.services.pipecat.kenyan_transcript_processor.kenyan_telephony_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "api.services.pipecat.kenyan_transcript_processor.process_kenya_turn",
        lambda text, session_id="telephony", organization_id=None: KenyaTurn(
            original_transcript=text,
            normalized_transcript="normalized",
            language=LanguageGuess(
                language=KenyaLanguage.MIXED,
                primary_language=KenyaLanguage.MIXED,
                secondary_language=None,
                confidence=0.5,
                mix=ConversationalMix.NONE,
                style=DetectedStyle.NEUTRAL,
                swahili_hits=0,
                sheng_hits=0,
                english_hits=0,
            ),
            intent=None,
            entities=ExtractedEntities(),
        ),
    )
    monkeypatch.setattr(
        "api.services.pipecat.kenyan_transcript_processor.resolve_telephony_intent",
        lambda *a, **k: None,
    )

    processor = KenyanTranscriptProcessor()
    pushed = []

    async def capture(frame, direction):
        pushed.append(frame)

    processor.push_frame = capture  # type: ignore[method-assign]

    frame = TranscriptionFrame(text="msee", user_id="u1", timestamp="t1")
    await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

    assert pushed[0].text == "normalized"
    assert pushed[0].original_transcript == "msee"


@pytest.mark.asyncio
async def test_mpesa_crm_sync_records_payment(monkeypatch):
    from api.services.mpesa_daraja.crm_sync import sync_completed_transaction_to_crm

    monkeypatch.setattr("api.services.mpesa_daraja.crm_sync.CRM_ENABLED", True)

    tx = MagicMock()
    tx.status = "completed"
    tx.amount = 500.0
    tx.currency = "KES"
    tx.phone_e164 = "+254712345678"
    tx.workflow_run_id = 9
    tx.mpesa_receipt_number = "ABC123"
    tx.account_reference = "INV-1"
    tx.metadata_json = {"customer_id": 42}

    with (
        patch("api.services.mpesa_daraja.crm_sync.db_client") as mock_db,
        patch("api.services.mpesa_daraja.crm_sync.get_customer_service") as mock_svc,
    ):
        mock_db.get_transaction = AsyncMock(return_value=tx)
        mock_db.get_payment_by_mpesa_transaction_id = AsyncMock(return_value=None)
        svc = MagicMock()
        svc.enabled = True
        svc.record_payment = AsyncMock()
        mock_svc.return_value = svc

        ok = await sync_completed_transaction_to_crm(1, organization_id=7)

    assert ok is True
    svc.record_payment.assert_awaited_once()
    kwargs = svc.record_payment.await_args.kwargs
    assert kwargs["mpesa_transaction_id"] == 1
    assert kwargs["organization_id"] == 7
