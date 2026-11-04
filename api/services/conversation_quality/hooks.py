"""Workflow completion hook for automated quality evaluation."""

from __future__ import annotations

from api.constants import CONVERSATION_QUALITY_ENABLED
from api.services.conversation_quality.pipeline import get_conversation_quality_pipeline


async def on_workflow_run_completed(workflow_run_id: int) -> None:
    if not CONVERSATION_QUALITY_ENABLED:
        return
    await get_conversation_quality_pipeline().evaluate_workflow_run(workflow_run_id)
