"""Campaign retry engine — centralized retry decisions and scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from api.constants import DEFAULT_CAMPAIGN_RETRY_CONFIG
from api.db import db_client
from api.db.models import QueuedRunModel


class CampaignRetryEngine:
    """Evaluate telephony outcomes and schedule campaign retries."""

    def should_retry(
        self,
        *,
        reason: str,
        retry_count: int,
        retry_config: dict[str, Any] | None,
    ) -> bool:
        config = retry_config or DEFAULT_CAMPAIGN_RETRY_CONFIG
        if not config.get("enabled", True):
            return False

        reason_map = {
            "busy": config.get("retry_on_busy", True),
            "no_answer": config.get("retry_on_no_answer", True),
            "no-answer": config.get("retry_on_no_answer", True),
            "voicemail": config.get("retry_on_voicemail", False),
        }
        if not reason_map.get(reason, False):
            return False

        max_retries = int(config.get("max_retries", 1))
        return retry_count < max_retries

    def compute_delay_s(
        self,
        *,
        retry_count: int,
        retry_config: dict[str, Any] | None,
        priority_score: float | None = None,
    ) -> int:
        config = retry_config or DEFAULT_CAMPAIGN_RETRY_CONFIG
        base = int(config.get("retry_delay_seconds", 120))
        delay = base * (2 ** max(0, retry_count - 1))
        if priority_score is not None and priority_score >= 65:
            delay = int(delay * 0.75)
        elif priority_score is not None and priority_score < 30:
            delay = int(delay * 1.25)
        return min(delay, 86400 * 3)

    async def schedule_retry(
        self,
        original_run: QueuedRunModel,
        *,
        reason: str,
        retry_config: dict[str, Any] | None = None,
    ) -> QueuedRunModel | None:
        config = retry_config or DEFAULT_CAMPAIGN_RETRY_CONFIG
        if not self.should_retry(
            reason=reason,
            retry_count=original_run.retry_count,
            retry_config=config,
        ):
            await self._mark_final_failure(original_run, reason)
            return None

        priority_score = None
        ctx = original_run.context_variables or {}
        if ctx.get("priority_score") is not None:
            try:
                priority_score = float(ctx["priority_score"])
            except (TypeError, ValueError):
                priority_score = None

        delay_s = self.compute_delay_s(
            retry_count=original_run.retry_count + 1,
            retry_config=config,
            priority_score=priority_score,
        )

        retry_context = {
            **ctx,
            "is_retry": True,
            "retry_attempt": original_run.retry_count + 1,
            "retry_reason": reason,
        }

        retry_run = await db_client.create_queued_run(
            campaign_id=original_run.campaign_id,
            source_uuid=f"{original_run.source_uuid}_retry_{original_run.retry_count + 1}",
            context_variables=retry_context,
            state="queued",
            retry_count=original_run.retry_count + 1,
            parent_queued_run_id=original_run.id,
            scheduled_for=datetime.now(UTC) + timedelta(seconds=delay_s),
            retry_reason=reason,
        )
        logger.info(
            "scheduled campaign retry run={} campaign={} reason={} delay={}s",
            retry_run.id,
            original_run.campaign_id,
            reason,
            delay_s,
        )
        return retry_run

    async def _mark_final_failure(self, queued_run: QueuedRunModel, reason: str) -> None:
        campaign = await db_client.get_campaign_by_id(queued_run.campaign_id)
        if campaign:
            await db_client.update_campaign(
                campaign_id=queued_run.campaign_id,
                failed_rows=campaign.failed_rows + 1,
            )
        logger.info(
            "max retries reached queued_run={} campaign={} reason={}",
            queued_run.id,
            queued_run.campaign_id,
            reason,
        )
