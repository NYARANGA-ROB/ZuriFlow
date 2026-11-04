"""Wire Kenyan normalization and intent into telephony (Pipecat) pipelines."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.constants import (
    KENYAN_CONVERSATION_ENABLED,
    KENYAN_INTENT_ENABLED,
    KENYAN_NORMALIZE_ENABLED,
)


def kenyan_telephony_enabled() -> bool:
    return KENYAN_NORMALIZE_ENABLED or KENYAN_CONVERSATION_ENABLED


def normalize_telephony_transcript(text: str) -> str:
    """Normalize caller STT text on telephony/WebRTC Pipecat paths."""
    if not text or not kenyan_telephony_enabled():
        return text.strip() if text else text

    if KENYAN_CONVERSATION_ENABLED:
        try:
            from api.services.kenyan_conversation.integration import (
                get_kenyan_conversation_behavior,
            )

            behavior = get_kenyan_conversation_behavior()
            if behavior.enabled:
                return behavior.normalize_caller_text(text)
        except Exception as e:
            logger.debug("Kenyan conversation normalize skipped: {}", e)

    if KENYAN_NORMALIZE_ENABLED:
        try:
            from api.services.kenyan_normalize.integration import normalize_transcript

            return normalize_transcript(text).normalized
        except Exception as e:
            logger.debug("Kenyan normalize skipped: {}", e)

    return text.strip()


def resolve_telephony_intent(text: str, *, session_id: str) -> dict[str, Any] | None:
    """Classify low-latency business intent for routing (optional)."""
    if not KENYAN_INTENT_ENABLED or not text.strip():
        return None
    try:
        from api.services.kenyan_intent.service import get_realtime_intent_service

        svc = get_realtime_intent_service()
        if not svc.enabled:
            return None
        result, route = svc.infer_sync(session_id, text)
        return {
            "intent": result.intent.value,
            "confidence": result.confidence,
            "language": result.language,
            "route_action": route.action.value if route else None,
        }
    except Exception as e:
        logger.debug("Telephony intent resolve skipped: {}", e)
        return None
