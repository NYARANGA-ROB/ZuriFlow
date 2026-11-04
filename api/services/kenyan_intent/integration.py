from __future__ import annotations

from api.constants import KENYAN_INTENT_ENABLED
from api.services.kenyan_intent.service import RealtimeIntentInferenceService, get_realtime_intent_service
from api.services.kenyan_intent.types import BusinessIntent, RouteAction, TranscriptKind

_VOICE_MPESA_INTENTS = {
    BusinessIntent.PAYMENT: "request_payment",
}


async def infer_caller_intent(
    session_id: str,
    text: str,
    *,
    is_final: bool = True,
    service: RealtimeIntentInferenceService | None = None,
):
    svc = service or get_realtime_intent_service()
    if not KENYAN_INTENT_ENABLED or not svc.enabled:
        return None, None
    kind = TranscriptKind.FINAL if is_final else TranscriptKind.PARTIAL
    return await svc.infer(session_id, text, kind=kind)


def system_hint_from_route(route) -> str | None:
    if route is None or route.action == RouteAction.CONTINUE:
        return None
    return (
        f"[Caller intent: {route.intent.value} — {route.reason}. "
        f"Suggested action: {route.action.value}.]"
    )


def voice_mpesa_intent_from_route(route) -> str | None:
    if route is None:
        return None
    return _VOICE_MPESA_INTENTS.get(route.intent)


def kenyan_intent_enabled_for_session(metadata: dict | None) -> bool:
    if not KENYAN_INTENT_ENABLED:
        return False
    meta = metadata or {}
    if "kenyan_intent_enabled" in meta:
        return bool(meta["kenyan_intent_enabled"])
    return True
