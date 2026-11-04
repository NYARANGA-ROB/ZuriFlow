from __future__ import annotations

from typing import Any

from api.services.whatsapp.post_call.orchestrator import PostCallWhatsAppOrchestrator


async def run_post_call_whatsapp_workflow(
    workflow_run_id: int,
    *,
    resume_from_step: str | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    """Run the automated post-call WhatsApp workflow for a completed voice call."""
    orchestrator = PostCallWhatsAppOrchestrator()
    result = await orchestrator.run(
        workflow_run_id,
        resume_from_step=resume_from_step,
        attempt=attempt,
    )
    return result.to_dict()


async def send_post_call_whatsapp_summary(
    *,
    organization_id: int,
    phone_e164: str,
    workflow_run_id: int,
    memory_snapshot: dict[str, Any] | None = None,
    gathered_context: dict[str, Any] | None = None,
    customer_name: str = "there",
) -> dict[str, Any]:
    """Backward-compatible helper that runs the full post-call workflow."""
    if memory_snapshot or gathered_context:
        from api.db import db_client

        patch: dict[str, Any] = {}
        if memory_snapshot:
            patch["conversation_memory"] = memory_snapshot
        if gathered_context:
            patch.update(gathered_context)
        if customer_name != "there":
            patch["customer_name"] = customer_name
        if phone_e164:
            patch["whatsapp_phone"] = phone_e164
        if patch:
            await db_client.update_workflow_run(
                run_id=workflow_run_id,
                gathered_context=patch,
                initial_context={"customer_name": customer_name} if customer_name != "there" else None,
            )
    return await run_post_call_whatsapp_workflow(workflow_run_id)
