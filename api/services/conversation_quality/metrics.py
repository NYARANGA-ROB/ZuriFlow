"""QA metrics extraction from workflow runs and realtime feedback events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pipecat.utils.enums import RealtimeFeedbackType

from api.services.workflow.qa.metrics import compute_call_metrics


def extract_feedback_events(workflow_run) -> list[dict]:
    logs = getattr(workflow_run, "logs", None) or {}
    return list(logs.get("realtime_feedback_events") or [])


def extract_qa_annotations(workflow_run) -> dict[str, Any]:
    annotations = getattr(workflow_run, "annotations", None) or {}
    qa: dict[str, Any] = {}
    for key, value in annotations.items():
        if not key.startswith("qa_") or not isinstance(value, dict):
            continue
        qa[key] = value
    return qa


def collect_qa_tags(qa_annotations: dict[str, Any]) -> list[dict[str, Any]]:
    tags: list[dict[str, Any]] = []
    for result in qa_annotations.values():
        if result.get("skipped") or result.get("error"):
            continue
        for node_result in (result.get("node_results") or {}).values():
            for tag in node_result.get("tags") or []:
                if isinstance(tag, dict):
                    tags.append(tag)
                elif isinstance(tag, str):
                    tags.append({"tag": tag})
        for tag in result.get("tags") or []:
            if isinstance(tag, dict):
                tags.append(tag)
    return tags


def collect_qa_scores(qa_annotations: dict[str, Any]) -> list[float]:
    scores: list[float] = []
    for result in qa_annotations.values():
        for node_result in (result.get("node_results") or {}).values():
            score = node_result.get("score")
            if score is not None:
                try:
                    scores.append(float(score))
                except (TypeError, ValueError):
                    pass
    return scores


def build_evaluation_context(workflow_run) -> dict[str, Any]:
    """Aggregate all signals used by dimension scorers."""
    events = extract_feedback_events(workflow_run)
    usage = getattr(workflow_run, "usage_info", None) or {}
    gathered = getattr(workflow_run, "gathered_context", None) or {}
    initial = getattr(workflow_run, "initial_context", None) or {}
    qa_annotations = extract_qa_annotations(workflow_run)

    call_duration = usage.get("call_duration_seconds")
    base_metrics = compute_call_metrics(events, call_duration)
    speaking = _speaking_timeline(events)
    interruptions = _detect_interruptions(events, speaking)
    bot_texts, user_texts = _utterance_texts(events)
    pipeline_errors = _count_event_type(events, RealtimeFeedbackType.PIPELINE_ERROR.value)

    debt = gathered.get("debt_collection") or {}
    payment = gathered.get("payment") or debt.get("payment") or {}

    return {
        "events": events,
        "usage_info": usage,
        "gathered_context": gathered,
        "initial_context": initial,
        "qa_annotations": qa_annotations,
        "qa_tags": collect_qa_tags(qa_annotations),
        "qa_scores": collect_qa_scores(qa_annotations),
        "call_metrics": base_metrics,
        "speaking_timeline": speaking,
        "interruptions": interruptions,
        "bot_utterances": bot_texts,
        "user_utterances": user_texts,
        "pipeline_error_count": pipeline_errors,
        "negotiation_outcome": (
            debt.get("negotiation_outcome")
            or gathered.get("negotiation_outcome")
            or payment.get("outcome")
        ),
        "payment_collected": _payment_collected(gathered, debt, payment),
        "escalated": bool(
            debt.get("escalated")
            or gathered.get("escalated")
            or gathered.get("human_escalation")
        ),
        "disposition": gathered.get("mapped_call_disposition")
        or gathered.get("call_disposition"),
    }


def _payment_collected(gathered: dict, debt: dict, payment: dict) -> bool:
    if payment.get("collected") or payment.get("success"):
        return True
    if debt.get("payment_collected"):
        return True
    disposition = (gathered.get("mapped_call_disposition") or "").lower()
    return disposition in {"payment_collected", "paid", "repayment_collected", "success"}


def _count_event_type(events: list[dict], event_type: str) -> int:
    return sum(1 for e in events if e.get("type") == event_type)


def _utterance_texts(events: list[dict]) -> tuple[list[str], list[str]]:
    bot: list[str] = []
    user: list[str] = []
    for event in events:
        etype = event.get("type")
        payload = event.get("payload") or {}
        if etype == RealtimeFeedbackType.BOT_TEXT.value:
            text = (payload.get("text") or "").strip()
            if text:
                bot.append(text)
        elif etype == RealtimeFeedbackType.USER_TRANSCRIPTION.value and payload.get("final"):
            text = (payload.get("text") or "").strip()
            if text:
                user.append(text)
    return bot, user


def _parse_ts(event: dict) -> datetime | None:
    payload = event.get("payload") or {}
    for candidate in (payload.get("timestamp"), event.get("timestamp")):
        if not candidate:
            continue
        try:
            return datetime.fromisoformat(str(candidate).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
    return None


def _speaking_timeline(events: list[dict]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    bot_speaking = False
    for event in events:
        etype = event.get("type")
        ts = _parse_ts(event)
        if etype == RealtimeFeedbackType.BOT_STARTED_SPEAKING.value:
            bot_speaking = True
            timeline.append({"state": "bot_speaking_start", "ts": ts})
        elif etype == RealtimeFeedbackType.BOT_STOPPED_SPEAKING.value:
            bot_speaking = False
            timeline.append({"state": "bot_speaking_stop", "ts": ts})
        elif (
            etype == RealtimeFeedbackType.USER_TRANSCRIPTION.value
            and (event.get("payload") or {}).get("final")
        ):
            timeline.append(
                {"state": "user_turn", "ts": ts, "during_bot_speech": bot_speaking}
            )
    return timeline


def _detect_interruptions(
    events: list[dict], timeline: list[dict[str, Any]]
) -> dict[str, Any]:
    user_during_bot = [t for t in timeline if t.get("during_bot_speech")]
    handled = 0
    for turn in user_during_bot:
        ts = turn.get("ts")
        if ts is None:
            continue
        for marker in timeline:
            if marker.get("state") != "bot_speaking_stop":
                continue
            stop_ts = marker.get("ts")
            if stop_ts and stop_ts >= ts:
                delta = (stop_ts - ts).total_seconds()
                if delta <= 3.0:
                    handled += 1
                break

    total = len(user_during_bot)
    return {
        "total": total,
        "handled_within_3s": handled,
        "unhandled": max(total - handled, 0),
    }
