"""Normalize provider webhooks into CallEvent values."""

from __future__ import annotations

from api.services.telephony.domain import CallEvent, CallEventType

_STATUS_MAP: dict[str, CallEventType] = {
    "queued": CallEventType.CALL_STARTED,
    "initiated": CallEventType.CALL_STARTED,
    "started": CallEventType.CALL_STARTED,
    "active": CallEventType.CALL_ANSWERED,
    "ringing": CallEventType.CALL_RINGING,
    "ring": CallEventType.CALL_RINGING,
    "answered": CallEventType.CALL_ANSWERED,
    "in-progress": CallEventType.CALL_ANSWERED,
    "in_progress": CallEventType.CALL_ANSWERED,
    "completed": CallEventType.CALL_ENDED,
    "complete": CallEventType.CALL_ENDED,
    "hangup": CallEventType.CALL_ENDED,
    "failed": CallEventType.CALL_FAILED,
    "busy": CallEventType.CALL_FAILED,
    "no-answer": CallEventType.CALL_FAILED,
    "no_answer": CallEventType.CALL_FAILED,
    "canceled": CallEventType.CALL_FAILED,
    "cancelled": CallEventType.CALL_FAILED,
    "error": CallEventType.CALL_FAILED,
    "timeout": CallEventType.CALL_FAILED,
    "rejected": CallEventType.CALL_FAILED,
    "dtmf": CallEventType.DTMF_RECEIVED,
    "digits": CallEventType.DTMF_RECEIVED,
    "media": CallEventType.MEDIA_STARTED,
    "stream-started": CallEventType.MEDIA_STARTED,
    "stream_started": CallEventType.MEDIA_STARTED,
}

# After answer, a live customer is on the line — do not fail over.
_CUSTOMER_FACING = frozenset(
    {
        CallEventType.CALL_ANSWERED,
        CallEventType.MEDIA_STARTED,
        CallEventType.DTMF_RECEIVED,
        CallEventType.CALL_ENDED,
    }
)


def normalize_call_status(raw_status: str | None) -> CallEventType:
    key = (raw_status or "").strip().lower().replace(" ", "-")
    return _STATUS_MAP.get(key, CallEventType.CALL_STARTED if not key else CallEventType.CALL_FAILED)


def event_from_status_callback(
    *,
    workflow_run_id: int | None,
    call_id: str | None,
    status: str | None,
    extra: dict | None = None,
) -> CallEvent:
    extra = extra or {}
    event_type = normalize_call_status(status)
    digit = extra.get("Digits") or extra.get("dtmf") or extra.get("digit")
    if digit and event_type != CallEventType.DTMF_RECEIVED:
        event_type = CallEventType.DTMF_RECEIVED
    return CallEvent(
        type=event_type,
        workflow_run_id=workflow_run_id,
        provider_call_id=call_id,
        digit=str(digit) if digit is not None else None,
        raw_status=status,
        metadata={k: extra[k] for k in extra if k in {"CallStatus", "Event", "duration"}},
    )


def is_customer_facing(event_type: CallEventType) -> bool:
    return event_type in _CUSTOMER_FACING


def events_show_customer_on_line(events: list[dict] | list[CallEvent]) -> bool:
    for item in events:
        value = item.type if isinstance(item, CallEvent) else item.get("type")
        try:
            parsed = value if isinstance(value, CallEventType) else CallEventType(str(value))
        except ValueError:
            continue
        if is_customer_facing(parsed):
            return True
    return False
