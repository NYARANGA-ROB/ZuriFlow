"""CRM segment source sync for voice campaigns."""

from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger

from api.constants import CRM_ENABLED
from api.db import db_client
from api.services.campaign.source_sync import (
    CampaignSourceSyncService,
    ValidationError,
    ValidationResult,
)
from api.services.call_prioritization.service import get_call_prioritization_service
from api.services.crm.service import get_customer_service
from api.services.voice_campaign.scheduler import CampaignScheduler


def _parse_segment(source_id: str) -> dict[str, Any]:
    try:
        return json.loads(source_id)
    except json.JSONDecodeError:
        return {"segment": source_id or "all"}


class CrmSegmentSyncService(CampaignSourceSyncService):
    """Sync CRM customers into campaign queued runs with priority scores."""

    async def validate_source(
        self, source_id: str, organization_id: Optional[int] = None
    ) -> ValidationResult:
        if not CRM_ENABLED:
            return ValidationResult(
                is_valid=False,
                error=ValidationError(message="CRM is disabled"),
            )
        segment = _parse_segment(source_id)
        if organization_id is None:
            return ValidationResult(is_valid=True)
        customers = await db_client.list_customers(
            organization_id=organization_id,
            limit=int(segment.get("limit", 500)),
        )
        if not customers:
            return ValidationResult(
                is_valid=False,
                error=ValidationError(message="No CRM customers found for segment"),
            )
        return ValidationResult(is_valid=True)

    async def sync_source_data(self, campaign_id: int) -> int:
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        segment = _parse_segment(campaign.source_id)
        min_outstanding = float(segment.get("min_outstanding", 0))
        limit = int(segment.get("limit", 500))
        default_locale = str(segment.get("default_locale", "mixed"))
        use_priority = bool(segment.get("use_priority", True))

        customers = await db_client.list_customers(
            organization_id=campaign.organization_id,
            limit=limit,
        )

        crm = get_customer_service()
        prioritizer = get_call_prioritization_service()
        scheduler = CampaignScheduler()
        meta = campaign.orchestrator_metadata or {}
        locale_cfg = meta.get("locale_config") or {}

        scores: dict[int, float] = {}
        if use_priority and prioritizer.enabled:
            ids = [c.id for c in customers]
            if ids:
                ranked = await prioritizer.prioritize_batch(
                    ids,
                    organization_id=campaign.organization_id,
                )
                scores = {s.customer_id: s.score for s in ranked}

        queued_runs = []
        for customer in customers:
            profile = await crm.get_profile(customer.id, organization_id=campaign.organization_id)
            if profile is None:
                continue
            if profile.total_outstanding < min_outstanding:
                continue

            locale = scheduler.resolve_locale(
                {"preferred_locale": profile.preferred_locale},
                default_locale=locale_cfg.get("default_locale", default_locale),
            )

            debt_ref = ""
            if profile.debt_accounts:
                debt_ref = str(profile.debt_accounts[0].get("account_reference", ""))

            context_vars = {
                "phone_number": profile.phone_e164,
                "customer_name": profile.full_name,
                "customer_id": profile.id,
                "preferred_locale": locale,
                "locale": locale,
                "priority_score": scores.get(profile.id, 50.0),
                "outstanding_balance": profile.total_outstanding,
                "account_reference": debt_ref,
            }

            queued_runs.append(
                {
                    "campaign_id": campaign_id,
                    "source_uuid": f"crm_{profile.customer_uuid}",
                    "context_variables": context_vars,
                    "state": "queued",
                }
            )

        if queued_runs:
            await db_client.bulk_create_queued_runs(queued_runs)
            logger.info(
                "CRM segment sync created {} queued runs for campaign {}",
                len(queued_runs),
                campaign_id,
            )
        return len(queued_runs)
