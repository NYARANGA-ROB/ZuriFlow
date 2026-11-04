"""Outbound campaign queue — priority-aware claim over QueuedRun rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from api.db import db_client
from api.db.models import QueuedRunModel
from api.services.voice_campaign.config import ThrottleConfig
from api.services.voice_campaign.scheduler import CampaignScheduler
from api.services.voice_campaign.types import CampaignQueueStats


class OutboundCampaignQueue:
    """Manage outbound dial queue with scheduling and priority ordering."""

    def __init__(self, scheduler: CampaignScheduler | None = None) -> None:
        self._scheduler = scheduler or CampaignScheduler()

    async def claim_batch(
        self,
        campaign_id: int,
        *,
        limit: int = 10,
        use_priority: bool = True,
        respect_contact_timezone: bool = True,
    ) -> list[QueuedRunModel]:
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            return []

        claimed = await db_client.claim_queued_runs_for_processing(
            campaign_id=campaign_id,
            scheduled_before=datetime.now(UTC),
            limit=limit,
            use_priority=use_priority,
        )

        if not respect_contact_timezone or not claimed:
            return claimed

        meta = campaign.orchestrator_metadata or {}
        tz_field = str(meta.get("contact_timezone_field", "timezone"))
        callable_runs: list[QueuedRunModel] = []
        deferred: list[QueuedRunModel] = []

        for run in claimed:
            if self._scheduler.is_contact_callable(
                run.context_variables or {},
                campaign=campaign,
                contact_timezone_field=tz_field,
            ):
                callable_runs.append(run)
            else:
                deferred.append(run)

        for run in deferred:
            await db_client.update_queued_run(
                queued_run_id=run.id,
                state="queued",
            )
            logger.debug(
                "deferred queued_run {} — outside contact timezone window",
                run.id,
            )

        return callable_runs

    async def stats(self, campaign_id: int) -> CampaignQueueStats:
        breakdown = await db_client.get_queued_run_state_breakdown(campaign_id)
        scheduled = await db_client.get_scheduled_runs_count(campaign_id)
        total = sum(breakdown.values())
        return CampaignQueueStats(
            campaign_id=campaign_id,
            queued=breakdown.get("queued", 0),
            processing=breakdown.get("processing", 0),
            processed=breakdown.get("processed", 0),
            failed=breakdown.get("failed", 0),
            scheduled_retries=scheduled,
            total=total,
        )

    async def pending_count(self, campaign_id: int) -> int:
        stats = await self.stats(campaign_id)
        return stats.queued + stats.scheduled_retries

    async def list_preview(
        self,
        campaign_id: int,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        rows = await db_client.list_queued_runs_preview(
            campaign_id,
            limit=limit,
            use_priority=True,
        )
        return rows
