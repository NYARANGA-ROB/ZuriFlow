"""ARQ jobs for Digital Twin sync and webhook processing. Never on the audio loop."""

from __future__ import annotations

from datetime import UTC, datetime

from loguru import logger

from api.db import db_client
from api.services.business_twin import service


async def sync_business_source(ctx, organization_id: int, source_id: int):
    await service.run_sync(organization_id, source_id, correlation_id=str(ctx.get("job_id") if isinstance(ctx, dict) else ""))


async def process_business_event(
    ctx,
    organization_id: int,
    source_id: int,
    event_type: str,
    payload: dict,
):
    await service.ingest_event(organization_id, source_id, event_type, payload)


async def process_due_business_syncs(ctx):
    jobs = await db_client.due_sync_jobs(datetime.now(UTC))
    from api.tasks.arq import enqueue_job
    from api.tasks.function_names import FunctionNames

    for job in jobs:
        if job.lock_until and job.lock_until > datetime.now(UTC):
            continue
        logger.info("Queueing business sync org={} source={}", job.organization_id, job.source_id)
        await enqueue_job(FunctionNames.SYNC_BUSINESS_SOURCE, job.organization_id, job.source_id)
