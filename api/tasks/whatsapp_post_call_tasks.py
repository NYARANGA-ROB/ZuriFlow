"""ARQ task for automated post-call WhatsApp workflow."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.services.whatsapp.post_call.orchestrator import PostCallWhatsAppOrchestrator


async def process_post_call_whatsapp(
    _ctx: dict[str, Any],
    workflow_run_id: int,
    resume_from_step: str | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    orchestrator = PostCallWhatsAppOrchestrator()
    result = await orchestrator.run(
        workflow_run_id,
        resume_from_step=resume_from_step,
        attempt=attempt,
    )
    if not result.success and not result.skipped:
        logger.warning(
            "Post-call WhatsApp workflow incomplete run_id={} attempt={}",
            workflow_run_id,
            attempt,
        )
    return result.to_dict()
