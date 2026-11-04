from __future__ import annotations

from api.constants import MPESA_ENABLED, VOICE_MPESA_ENABLED
from api.services.voice_mpesa.engine import VoiceMpesaWorkflowEngine, get_voice_mpesa_engine


async def bootstrap_voice_mpesa_session(
    engine: VoiceMpesaWorkflowEngine,
    *,
    session_id: str,
    organization_id: int,
    workflow_run_id: int,
    phone_e164: str,
    customer_name: str = "there",
    amount: float | None = None,
    language: str = "mixed",
) -> None:
    if organization_id <= 0 or not phone_e164:
        return
    await engine.ensure_session(
        session_id=session_id,
        organization_id=organization_id,
        workflow_run_id=workflow_run_id,
        phone_e164=phone_e164,
        customer_name=customer_name,
        amount=amount,
        language=language,
    )


def voice_mpesa_enabled_for_session(metadata: dict | None) -> bool:
    if not VOICE_MPESA_ENABLED or not MPESA_ENABLED:
        return False
    meta = metadata or {}
    return bool(meta.get("voice_mpesa_enabled", meta.get("mpesa_enabled", True)))
