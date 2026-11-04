"""Workflow completion hook for Kenyan continuous learning."""

from __future__ import annotations

from api.constants import KENYAN_CONTINUOUS_LEARNING_ENABLED
from api.services.kenyan_continuous_learning.data_pipeline import get_kenyan_data_pipeline
from api.services.kenyan_continuous_learning.labeling import get_labeling_workflow


async def on_workflow_run_completed(workflow_run_id: int, organization_id: int) -> None:
    if not KENYAN_CONTINUOUS_LEARNING_ENABLED:
        return
    pipeline = get_kenyan_data_pipeline()
    sample_ids = await pipeline.collect_from_workflow_run(workflow_run_id)
    if sample_ids:
        await get_labeling_workflow().enqueue_from_samples(organization_id, sample_ids)
