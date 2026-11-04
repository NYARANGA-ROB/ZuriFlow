"""Call-quality diagnostics from pipeline metrics and telephony events."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.services.telephony.call_events import CallEventType, normalize_call_status


def build_quality_report(run) -> dict[str, Any]:
    usage = run.usage_info or {}
    extra = run.extra or {}
    logs = run.logs or {}
    quality = extra.get("call_quality") or usage.get("call_quality") or {}
    events = logs.get("call_events") or []
    callbacks = logs.get("telephony_status_callbacks") or []

    failed = any(
        (item.get("type") if isinstance(item, dict) else None)
        == CallEventType.CALL_FAILED.value
        for item in events
    ) or any(
        normalize_call_status(cb.get("status")).value == CallEventType.CALL_FAILED.value
        for cb in callbacks
        if isinstance(cb, dict)
    )

    stt = _num(quality.get("stt_latency_ms") or usage.get("stt_latency_ms"))
    llm = _num(quality.get("llm_latency_ms") or usage.get("llm_latency_ms"))
    tts = _num(quality.get("tts_latency_ms") or usage.get("tts_latency_ms"))
    total = _num(
        quality.get("total_response_latency_ms")
        or usage.get("user_to_bot_latency_ms")
        or _sum_present(stt, llm, tts)
    )

    return {
        "workflow_run_id": run.id,
        "latency_ms": {
            "network": _num(quality.get("network_latency_ms") or quality.get("rtt_ms")),
            "stt": stt,
            "llm": llm,
            "tts": tts,
            "total_response": total,
        },
        "packet_loss": quality.get("packet_loss"),
        "call_failed": failed,
        "event_count": len(events),
        "provider": (run.gathered_context or {}).get("provider")
        or (run.initial_context or {}).get("provider"),
    }


async def get_call_quality(organization_id: int, workflow_run_id: int) -> dict[str, Any]:
    run, org_id = await db_client.get_workflow_run_with_context(workflow_run_id)
    if not run or org_id != organization_id:
        raise LookupError("workflow_run_not_found")
    return build_quality_report(run)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_present(*values: float | None) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present)
