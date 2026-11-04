"""Background tasks for Kenyan continuous learning retraining."""

from __future__ import annotations

from loguru import logger

from api.services.kenyan_continuous_learning.orchestrator import get_retraining_orchestrator


async def run_kenyan_continuous_learning_training(
    _ctx,
    organization_id: int,
    *,
    targets: list[str] | None = None,
    days: int = 30,
    auto_apply: bool = False,
) -> dict:
    """Run dataset build and artifact derivation for one organization."""
    logger.info("Starting Kenyan CL training for org {}", organization_id)
    return await get_retraining_orchestrator().start_run(
        organization_id,
        targets=targets,
        days=days,
        auto_apply=auto_apply,
    )
