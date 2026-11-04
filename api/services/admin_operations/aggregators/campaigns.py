"""Campaign tracking aggregation."""

from __future__ import annotations

from typing import Any

from api.constants import VOICE_CAMPAIGN_ENABLED
from api.db import db_client
from api.services.voice_campaign.service import get_voice_campaign_service


class CampaignsAggregator:
    async def list_campaigns(
        self,
        organization_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        campaigns = await db_client.get_campaigns(organization_id)
        total = len(campaigns)
        page = campaigns[offset : offset + limit]
        items: list[dict[str, Any]] = []
        voice_svc = get_voice_campaign_service() if VOICE_CAMPAIGN_ENABLED else None
        for campaign in page:
            entry: dict[str, Any] = {
                "id": campaign.id,
                "name": campaign.name,
                "state": campaign.state,
                "workflow_id": campaign.workflow_id,
                "total_rows": campaign.total_rows,
                "processed_rows": campaign.processed_rows,
                "failed_rows": campaign.failed_rows,
                "created_at": campaign.created_at.isoformat()
                if campaign.created_at
                else None,
            }
            if voice_svc and voice_svc.enabled:
                analytics = await voice_svc.get_analytics(campaign.id)
                if analytics:
                    entry["analytics"] = analytics
            items.append(entry)
        return {
            "organization_id": organization_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "campaigns": items,
        }

    async def campaign_detail(
        self, organization_id: int, campaign_id: int
    ) -> dict[str, Any] | None:
        campaign = await db_client.get_campaign(campaign_id, organization_id)
        if campaign is None:
            return None
        metrics = await db_client.get_campaign_run_metrics(campaign_id)
        analytics = None
        if VOICE_CAMPAIGN_ENABLED:
            analytics = await get_voice_campaign_service().get_analytics(campaign_id)
        return {
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "state": campaign.state,
                "workflow_id": campaign.workflow_id,
                "total_rows": campaign.total_rows,
                "processed_rows": campaign.processed_rows,
                "failed_rows": campaign.failed_rows,
            },
            "run_metrics": metrics,
            "analytics": analytics,
        }
