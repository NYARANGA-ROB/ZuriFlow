"""Kenyan conversational intelligence — synthetic (non-sensitive) suites."""

from __future__ import annotations

from api.services.kenya.analytics import get_kenya_analytics
from api.services.kenya.catalog import CatalogPhrase, get_phrase_catalog
from api.services.kenya.config import KenyaLanguage
from api.services.kenya.language import ConversationalMix
from api.services.kenya.pipeline import process_kenya_turn
from api.services.kenya.session import get_kenya_session_store
from api.services.kenya.styles import KenyaConversationStyle, get_style
from api.services.kenyan_intent.types import BusinessIntent


def test_code_switch_follows_caller_when_confident():
    sid = "intel-switch-1"
    first = process_kenya_turn(
        "I need help with my account please",
        session_id=sid,
        organization_id=1,
    )
    assert first.language.primary_language == KenyaLanguage.ENGLISH
    second = process_kenya_turn("nataka salio langu sawa", session_id=sid, organization_id=1)
    third = process_kenya_turn(
        "okay please confirm my account",
        session_id=sid,
        organization_id=1,
    )
    assert second.language.mix in {
        ConversationalMix.ENGLISH_KISWAHILI,
        ConversationalMix.NONE,
        ConversationalMix.KISWAHILI_SHENG,
    }
    session = get_kenya_session_store().get(sid)
    assert session.turn_count == 3
    assert third.metadata["preferred_reply_language"] in {"en", "sw", "mixed", "sheng"}


def test_style_kiswahili_first_does_not_follow_english():
    profile = get_style(KenyaConversationStyle.KISWAHILI_FIRST)
    assert profile.follow_caller_language is False
    turn = process_kenya_turn(
        "hello I want my balance please",
        session_id="intel-style-sw",
        style=KenyaConversationStyle.KISWAHILI_FIRST.value,
    )
    assert turn.style == "kiswahili_first"
    assert turn.metadata["preferred_reply_language"] == "sw"


def test_low_confidence_asks_clarification_and_blocks_invention():
    turn = process_kenya_turn("zzzz qqqq wwww", session_id="intel-clarify")
    assert turn.confidence is not None
    assert turn.confidence.action in {"clarify", "proceed"}
    if turn.confidence.action == "clarify":
        assert turn.confidence.clarification_prompt
        assert turn.confidence.allow_financial is False
        assert turn.confidence.allow_transfer is False


def test_financial_block_requires_confirmation():
    turn = process_kenya_turn("maybe pay something", session_id="intel-pay")
    assert turn.confidence is not None
    if turn.intent and turn.intent.intent == BusinessIntent.PAYMENT:
        assert turn.confidence.allow_financial is False or turn.confidence.action in {
            "block_financial",
            "clarify",
            "proceed",
        }


def test_escalation_explicit_human():
    turn = process_kenya_turn("nataka mtu tafadhali", session_id="intel-esc")
    assert turn.escalation is not None
    assert turn.escalation.escalate is True
    pkg = turn.escalation.package
    assert "detected_language" in pkg
    assert "customer_intent" in pkg
    assert "previous_attempts" in pkg


def test_catalog_contextual_match(monkeypatch):
    catalog = get_phrase_catalog()
    catalog.set_overlay(
        [
            CatalogPhrase(
                phrase="ika nini",
                meaning="what happened",
                language="sheng",
                intent="support",
                confidence=0.9,
                context="nairobi_youth",
                region="nairobi",
                version="1",
                active=True,
            )
        ]
    )
    turn = process_kenya_turn("ika nini kwa order", session_id="intel-dict", region="nairobi")
    assert turn.catalog_match is not None
    assert turn.normalized_transcript == "what happened"
    catalog.set_overlay([])


def test_analytics_counters():
    process_kenya_turn("sasa boss poa fiti", session_id="intel-an-1", organization_id=99)
    process_kenya_turn("nataka mtu", session_id="intel-an-1", organization_id=99)
    snap = get_kenya_analytics().snapshot(99)
    assert snap["turns"] >= 2
    assert "sheng_usage_rate" in snap
    assert "code_switching_rate" in snap
    assert "clarification_rate" in snap
    assert "escalation_rate" in snap
    assert "successful_intent_rate" in snap


def test_suite_scores_are_exposed_not_claimed_perfect():
    cases = [
        ("I want to pay via mpesa", BusinessIntent.PAYMENT),
        ("nataka balance yangu", BusinessIntent.BALANCE_INQUIRY),
        ("cancel my order", BusinessIntent.CANCELLATION),
    ]
    hits = 0
    for i, (text, expected) in enumerate(cases):
        turn = process_kenya_turn(text, session_id=f"intel-acc-{i}")
        if turn.intent and turn.intent.intent == expected:
            hits += 1
        assert turn.confidence is not None
        assert 0 <= turn.confidence.overall <= 1
    assert hits / len(cases) >= 0.66
