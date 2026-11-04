"""Campaign analytics pipeline."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.services.voice_analytics.emitter import get_voice_analytics_emitter
from api.services.voice_analytics.types import VoiceAnalyticsEvent, VoiceAnalyticsEventType
from api.services.voice_campaign.outbound_queue import OutboundCampaignQueue
from api.services.voice_campaign.types import CampaignAnalyticsSnapshot


ANSWERED_STATUSES = frozenset({"completed", "answered", "in-progress"})
FAILED_STATUSES = frozenset({"failed", "busy", "no-answer", "canceled", "error"})


class CampaignAnalyticsPipeline:
    """Aggregate campaign performance metrics."""

    def __init__(self, queue: OutboundCampaignQueue | None = None) -> None:
        self._queue = queue or OutboundCampaignQueue()

    async def snapshot(self, campaign_id: int) -> CampaignAnalyticsSnapshot | None:
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            return None

        queue_stats = await self._queue.stats(campaign_id)
        run_metrics = await db_client.get_campaign_run_metrics(campaign_id)

        total_attempts = run_metrics.get("total_runs", 0)
        answered = run_metrics.get("answered", 0)
        retries = run_metrics.get("retries", 0)

        answer_rate = (answered / total_attempts) if total_attempts else None
        retry_rate = (retries / total_attempts) if total_attempts else None

        return CampaignAnalyticsSnapshot(
            campaign_id=campaign_id,
            organization_id=campaign.organization_id,
            state=campaign.state,
            total_rows=campaign.total_rows or 0,
            processed_rows=campaign.processed_rows,
            failed_rows=campaign.failed_rows,
            queue=queue_stats,
            answer_rate=round(answer_rate, 4) if answer_rate is not None else None,
            retry_rate=round(retry_rate, 4) if retry_rate is not None else None,
            avg_call_duration_s=run_metrics.get("avg_duration_s"),
            outcomes=run_metrics.get("outcomes", {}),
            locales=run_metrics.get("locales", {}),
        )

    async def track_campaign_event(
        self,
        *,
        organization_id: int,
        campaign_id: int,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        get_voice_analytics_emitter().track(
            VoiceAnalyticsEvent(
                event_type=VoiceAnalyticsEventType.CAMPAIGN_EVENT,
                organization_id=organization_id,
                workflow_run_id=0,
                success=True,
                properties={
                    "campaign_id": campaign_id,
                    "event": event,
                    **(properties or {}),
                },
            )
        )

    async def track_batch_processed(
        self,
        *,
        organization_id: int,
        campaign_id: int,
        processed: int,
        failed: int,
    ) -> None:
        await self.track_campaign_event(
            organization_id=organization_id,
            campaign_id=campaign_id,
            event="batch_processed",
            properties={"processed": processed, "failed": failed},
        )
