"""Kenyan conversational intelligence: STT text → canonical turn for the workflow engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from api.services.kenya.analytics import get_kenya_analytics
from api.services.kenya.catalog import get_phrase_catalog
from api.services.kenya.confidence import ConfidenceDecision, decide_confidence
from api.services.kenya.config import KenyaLanguage
from api.services.kenya.entities import ExtractedEntities, extract_kenyan_entities
from api.services.kenya.escalation_policy import EscalationDecision, evaluate_escalation
from api.services.kenya.language import LanguageGuess, identify_kenya_language, lock_language
from api.services.kenya.session import get_kenya_session_store
from api.services.kenya.styles import KenyaConversationStyle, get_style
from api.services.kenyan_intent.types import BusinessIntent, ClassificationResult
from api.services.kenyan_normalize.types import NormalizeResult

_NOISE = re.compile(r"\b(uh+|um+|erm+|eee+)\b", re.I)
_REPEAT_CHAR = re.compile(r"(.)\1{3,}")


@dataclass
class KenyaTurn:
    original_transcript: str
    normalized_transcript: str
    language: LanguageGuess
    intent: ClassificationResult | None
    entities: ExtractedEntities
    confidence: ConfidenceDecision | None = None
    escalation: EscalationDecision | None = None
    style: str = KenyaConversationStyle.CUSTOMER_CARE.value
    catalog_match: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_transcript": self.original_transcript,
            "original_transcript": self.original_transcript,
            "normalized_transcript": self.normalized_transcript,
            "language": self.language.to_dict(),
            "intent": self.intent.to_dict() if self.intent else None,
            "entities": self.entities.to_safe_dict(),
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "escalation": self.escalation.to_dict() if self.escalation else None,
            "style": self.style,
            "catalog_match": self.catalog_match,
            "metadata": self.metadata,
        }


def process_kenya_turn(
    transcript: str,
    *,
    session_id: str = "kenya",
    classify_intent: bool = True,
    organization_id: int | None = None,
    style: str | None = None,
    region: str | None = None,
    follow_caller_language: bool | None = None,
    workflow_state: dict[str, Any] | None = None,
) -> KenyaTurn:
    original = transcript or ""
    cleaned = _spelling_noise_correction(original)
    language = identify_kenya_language(cleaned)

    store = get_kenya_session_store()
    session = store.get(session_id)
    style_profile = get_style(style or session.style)
    session.style = style_profile.style.value
    follow = (
        style_profile.follow_caller_language
        if follow_caller_language is None
        else follow_caller_language
    )
    if follow:
        language = lock_language(language, session.preferred_language)
    store.apply_language(session, language)

    catalog_hit = get_phrase_catalog().match(cleaned, region=region)
    catalog_text = catalog_hit.meaning if catalog_hit else cleaned

    from api.services.kenya_production.bottleneck_audit import StageTimer

    with StageTimer("normalize"):
        normalize_result = _normalize(catalog_text if catalog_hit else cleaned)
    normalized = (
        catalog_hit.meaning
        if catalog_hit
        else (normalize_result.normalized if normalize_result else cleaned)
    )

    intent: ClassificationResult | None = None
    if classify_intent:
        with StageTimer("intent"):
            intent = _classify(normalized, original=original)

    entities = extract_kenyan_entities(original)
    intent_enum = intent.intent if intent else None
    intent_conf = intent.confidence if intent else 0.0

    reply_lang = language.primary_language
    if not follow:
        reply_lang = {
            "sw": KenyaLanguage.KISWAHILI,
            "en": KenyaLanguage.ENGLISH,
            "sheng": KenyaLanguage.SHENG,
        }.get(style_profile.preferred_reply_language, language.primary_language)

    decision = decide_confidence(
        language_confidence=language.confidence,
        intent_confidence=intent_conf,
        intent=intent_enum,
        reply_language=reply_lang,
    )

    if decision.action == "clarify":
        session.clarification_count += 1
        session.low_confidence_streak += 1
        session.failed_recognition_count += 1
    else:
        session.low_confidence_streak = 0
        if intent_enum and intent_enum != BusinessIntent.UNKNOWN:
            session.intent_success_count += 1
            session.last_intents.append(intent_enum.value)

    session.raw_turns.append(original)
    if len(session.raw_turns) > 4:
        session.raw_turns = session.raw_turns[-4:]
    session.last_entities = entities.to_safe_dict()

    escalation = evaluate_escalation(
        session=session,
        raw=original,
        intent=intent_enum,
        language=language.primary_language.value,
        entities=entities.to_safe_dict(),
        confidence_action=decision.action,
        workflow_state=workflow_state,
    )
    if decision.action != "proceed" and not escalation.escalate:
        # Never invent meaning on a weak turn.
        if intent and intent.confidence < 0.5:
            intent.intent = BusinessIntent.UNKNOWN

    get_kenya_analytics().record(
        organization_id,
        {
            "primary_language": language.primary_language.value,
            "mix": language.mix.value,
            "sheng": language.sheng_hits > 0,
            "code_switched": language.switched,
            "failed_recognition": decision.action == "clarify",
            "clarification": decision.action == "clarify",
            "escalation": escalation.escalate,
            "intent_success": decision.action == "proceed"
            and intent_enum not in (None, BusinessIntent.UNKNOWN),
        },
    )

    if organization_id and organization_id > 0:
        try:
            from api.services.kenya_production.async_tasks import fire_and_forget

            fire_and_forget(
                store.persist_ephemeral(organization_id, session),
                name="kenya-session-redis",
            )
        except Exception:
            pass

    return KenyaTurn(
        original_transcript=original,
        normalized_transcript=normalized,
        language=language,
        intent=intent,
        entities=entities,
        confidence=decision,
        escalation=escalation,
        style=style_profile.style.value,
        catalog_match=catalog_hit.to_dict() if catalog_hit else None,
        metadata={
            "normalize_intent": getattr(normalize_result, "intent", None),
            "session_id": session_id,
            "session": session.snapshot(),
            "preferred_reply_language": (
                language.primary_language.value if follow else style_profile.preferred_reply_language
            ),
            "prompt_overlay": style_profile.prompt_overlay,
        },
    )


def _spelling_noise_correction(text: str) -> str:
    cleaned = _NOISE.sub(" ", text)
    cleaned = _REPEAT_CHAR.sub(r"\1\1", cleaned)
    cleaned = cleaned.replace("m pesa", "mpesa").replace("m-pesa", "mpesa")
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize(text: str) -> NormalizeResult | None:
    try:
        from api.services.kenyan_normalize.integration import normalize_transcript

        return normalize_transcript(text)
    except Exception:
        return None


def _classify(normalized: str, *, original: str) -> ClassificationResult | None:
    try:
        from api.services.kenyan_intent.classifier import KenyanIntentClassifier

        result = KenyanIntentClassifier().classify(original)
        result.original_text = original
        result.normalized_text = normalized
        return result
    except Exception:
        return None
