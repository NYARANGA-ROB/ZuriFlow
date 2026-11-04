"""Outbound DTMF helpers for telephony workflow runs."""

from __future__ import annotations

import re

from loguru import logger

from api.db import db_client

_DTMF_ALLOWED = re.compile(r"^[0-9*#wW,]+$")


def _sanitize_digits(digits: str) -> str:
    cleaned = "".join(ch for ch in digits if ch in "0123456789*#wW,")
    if not cleaned:
        raise ValueError("digits must contain at least one DTMF character")
    if not _DTMF_ALLOWED.match(cleaned):
        raise ValueError("digits contain invalid characters for DTMF")
    return cleaned


async def send_outbound_dtmf(engine, digits: str) -> dict:
    """Send DTMF tones on the active telephony call."""
    from api.services.telephony.factory import get_telephony_provider_for_run

    sanitized = _sanitize_digits(digits)
    workflow_run = await db_client.get_workflow_run_by_id(engine._workflow_run_id)
    if workflow_run is None:
        raise ValueError("workflow run not found")

    workflow = await db_client.get_workflow_by_id(workflow_run.workflow_id)
    if workflow is None:
        raise ValueError("workflow not found")

    gathered = dict(workflow_run.gathered_context or {})
    call_id = (
        gathered.get("call_id")
        or gathered.get("session_id")
        or gathered.get("CallUUID")
        or gathered.get("call_sid")
    )
    if not call_id:
        raise ValueError("active call_id not found on workflow run")

    provider = await get_telephony_provider_for_run(workflow_run, workflow.organization_id)
    if not provider.supports_dtmf():
        raise ValueError(
            f"Telephony provider {provider.PROVIDER_NAME} does not support outbound DTMF"
        )

    result = await provider.send_dtmf(str(call_id), sanitized)
    dtmf_sent = engine._gathered_context.get("dtmf_sent", "")
    engine._gathered_context["dtmf_sent"] = f"{dtmf_sent}{sanitized}"
    engine._gathered_context["last_dtmf_sent"] = sanitized
    logger.info(
        f"[run {engine._workflow_run_id}] Sent outbound DTMF '{sanitized}' via "
        f"{provider.PROVIDER_NAME}"
    )
    return result
