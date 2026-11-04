"""Voice campaign management service."""

from __future__ import annotations

from typing import Any

from api.constants import VOICE_CAMPAIGN_ENABLED
from api.db import db_client
from api.services.voice_campaign.analytics import CampaignAnalyticsPipeline
from api.services.voice_campaign.config import VoiceCampaignConfig
from api.services.voice_campaign.outbound_queue import OutboundCampaignQueue
from api.services.voice_campaign.retry_engine import CampaignRetryEngine
from api.services.voice_campaign.scheduler import CampaignScheduler
from api.services.voice_campaign.throttling import CampaignThrottler


class VoiceCampaignManagementService:
    """Unified engine for bulk outbound campaign operations."""

    def __init__(self) -> None:
        self._scheduler = CampaignScheduler()
        self._queue = OutboundCampaignQueue(self._scheduler)
        self._retry = CampaignRetryEngine()
        self._throttle = CampaignThrottler()
        self._analytics = CampaignAnalyticsPipeline(self._queue)

    @property
    def enabled(self) -> bool:
        return VOICE_CAMPAIGN_ENABLED

    async def configure_campaign(
        self,
        campaign_id: int,
        *,
        scheduled_start_at: str | None = None,
        locale_config: dict[str, Any] | None = None,
        throttle: dict[str, Any] | None = None,
        contact_timezone_field: str | None = None,
    ) -> dict[str, Any]:
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            raise ValueError("campaign_not_found")

        meta = dict(campaign.orchestrator_metadata or {})
        if scheduled_start_at is not None:
            meta["scheduled_start_at"] = scheduled_start_at
        if locale_config is not None:
            meta["locale_config"] = locale_config
        if throttle is not None:
            meta["throttle"] = {**(meta.get("throttle") or {}), **throttle}
        if contact_timezone_field is not None:
            meta["contact_timezone_field"] = contact_timezone_field
        meta["voice_campaign_enabled"] = True

        await db_client.update_campaign(
            campaign_id=campaign_id,
            orchestrator_metadata=meta,
        )
        return VoiceCampaignConfig.from_campaign(campaign).to_metadata_patch()

    async def start_campaign(self, campaign_id: int) -> None:
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            raise ValueError("campaign_not_found")
        if not self._scheduler.is_campaign_started(campaign):
            raise ValueError("campaign_scheduled_for_future")
        from api.services.campaign.runner import campaign_runner_service

        await campaign_runner_service.start_campaign(campaign_id)
        await self._analytics.track_campaign_event(
            organization_id=campaign.organization_id,
            campaign_id=campaign_id,
            event="started",
        )

    async def get_throttle_plan(self, campaign_id: int) -> dict[str, Any]:
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            raise ValueError("campaign_not_found")
        throttle_ctx = await self._throttle.throttle_context(campaign)
        queue_stats = await self._queue.stats(campaign_id)
        batch_size = self._throttle.compute_batch_size(
            VoiceCampaignConfig.from_campaign(campaign).throttle,
            queue_depth=queue_stats.queued + queue_stats.scheduled_retries,
        )
        return {**throttle_ctx, "suggested_batch_size": batch_size}

    async def claim_outbound_batch(
        self,
        campaign_id: int,
        *,
        batch_size: int | None = None,
    ) -> list[dict[str, Any]]:
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            return []
        if not self._scheduler.can_schedule_batch(campaign):
            return []

        throttle = VoiceCampaignConfig.from_campaign(campaign).throttle
        limit = batch_size or throttle.batch_size
        runs = await self._queue.claim_batch(
            campaign_id,
            limit=limit,
            use_priority=throttle.use_priority_queue,
        )
        return [
            {
                "id": r.id,
                "phone_number": (r.context_variables or {}).get("phone_number"),
                "priority_score": (r.context_variables or {}).get("priority_score"),
                "preferred_locale": (r.context_variables or {}).get("preferred_locale"),
                "retry_count": r.retry_count,
            }
            for r in runs
        ]

    async def schedule_retry_for_run(
        self,
        queued_run_id: int,
        *,
        reason: str,
    ) -> dict[str, Any] | None:
        queued_run = await db_client.get_queued_run_by_id(queued_run_id)
        if not queued_run:
            return None
        campaign = await db_client.get_campaign_by_id(queued_run.campaign_id)
        retry_run = await self._retry.schedule_retry(
            queued_run,
            reason=reason,
            retry_config=campaign.retry_config if campaign else None,
        )
        if retry_run is None:
            return {"scheduled": False, "reason": "max_retries_or_disabled"}
        return {"scheduled": True, "retry_run_id": retry_run.id, "delay_reason": reason}

    async def get_analytics(self, campaign_id: int) -> dict[str, Any] | None:
        snapshot = await self._analytics.snapshot(campaign_id)
        return snapshot.to_dict() if snapshot else None

    async def queue_preview(self, campaign_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
        return await self._queue.list_preview(campaign_id, limit=limit)

    async def refresh_priorities(
        self,
        campaign_id: int,
        *,
        organization_id: int,
    ) -> dict[str, Any]:
        from api.services.call_prioritization.service import get_call_prioritization_service

        rows = await db_client.list_queued_runs_preview(campaign_id, limit=500)
        prioritizer = get_call_prioritization_service()
        updated = 0

        for row in rows:
            run = await db_client.get_queued_run_by_id(row["id"])
            if not run:
                continue
            ctx = dict(run.context_variables or {})
            customer_id = ctx.get("customer_id")
            if not customer_id:
                continue
            scored = await prioritizer.score_customer(
                int(customer_id),
                organization_id=organization_id,
                track_analytics=False,
            )
            if not scored:
                continue
            ctx["priority_score"] = scored.score
            await db_client.update_queued_run(
                queued_run_id=run.id,
                context_variables=ctx,
            )
            updated += 1

        return {"updated": updated, "examined": len(rows)}

    async def cancel_campaign(self, campaign_id: int) -> None:
        from api.services.campaign.runner import campaign_runner_service

        await campaign_runner_service.cancel_campaign(campaign_id)


_service: VoiceCampaignManagementService | None = None


def get_voice_campaign_service() -> VoiceCampaignManagementService:
    global _service
    if _service is None:
        _service = VoiceCampaignManagementService()
    return _service
