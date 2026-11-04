"""Async call prioritization service."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.constants import CALL_PRIORITIZATION_ENABLED
from api.db import db_client
from api.enums import OrganizationConfigurationKey
from api.services.call_prioritization.analytics import (
    track_call_outcome_recorded,
    track_priority_queued,
    track_priority_scored,
    track_retry_scheduled,
)
from api.services.call_prioritization.config import (
    DEFAULT_PRIORITIZATION_CONFIG,
    CallPrioritizationConfig,
)
from api.services.call_prioritization.features import build_signals_from_profile
from api.services.call_prioritization.queue import PrioritizationQueue, PrioritizationRetryQueue
from api.services.call_prioritization.retry_scheduler import CallRetryScheduler
from api.services.call_prioritization.scoring import CallPrioritizationScoringEngine
from api.services.call_prioritization.types import (
    PrioritizedCallEntry,
    PrioritizationScore,
)
from api.services.crm.service import get_customer_service
from api.services.kenya_production.async_tasks import gather_with_concurrency


class CallPrioritizationService:
    """Score customers, manage priority queue, and schedule retries."""

    def __init__(
        self,
        *,
        config: CallPrioritizationConfig | None = None,
        scoring_engine: CallPrioritizationScoringEngine | None = None,
        queue: PrioritizationQueue | None = None,
        retry_queue: PrioritizationRetryQueue | None = None,
        retry_scheduler: CallRetryScheduler | None = None,
    ) -> None:
        self._config = config or DEFAULT_PRIORITIZATION_CONFIG
        self._scoring = scoring_engine or CallPrioritizationScoringEngine(self._config)
        self._queue = queue or PrioritizationQueue(ttl_s=self._config.queue_ttl_s)
        self._retry_queue = retry_queue or PrioritizationRetryQueue()
        self._retry_scheduler = retry_scheduler or CallRetryScheduler(self._config)

    @property
    def enabled(self) -> bool:
        return CALL_PRIORITIZATION_ENABLED and self._config.enabled

    async def load_org_config(self, organization_id: int) -> CallPrioritizationConfig:
        try:
            row = await db_client.get_configuration(
                organization_id,
                OrganizationConfigurationKey.CALL_PRIORITIZATION_CONFIGURATION.value,
            )
            return CallPrioritizationConfig.from_dict(row.value if row else None)
        except Exception:
            logger.exception("failed to load prioritization config org={}", organization_id)
            return DEFAULT_PRIORITIZATION_CONFIG

    async def score_customer(
        self,
        customer_id: int,
        *,
        organization_id: int,
        track_analytics: bool = True,
    ) -> PrioritizationScore | None:
        profile = await self._load_profile(customer_id, organization_id=organization_id)
        if profile is None:
            return None
        signals = build_signals_from_profile(profile)
        result = self._scoring.score(signals)
        if track_analytics:
            track_priority_scored(
                organization_id=organization_id,
                customer_id=customer_id,
                score=result.score,
                tier=result.tier,
                likely_payer=result.likely_payer,
            )
        return result

    async def prioritize_batch(
        self,
        customer_ids: list[int],
        *,
        organization_id: int,
        concurrency: int = 10,
    ) -> list[PrioritizationScore]:
        org_config = await self.load_org_config(organization_id)
        self._apply_config(org_config)

        async def _score(cid: int) -> PrioritizationScore | None:
            return await self.score_customer(cid, organization_id=organization_id)

        results = await gather_with_concurrency(customer_ids, _score, limit=concurrency)
        scored: list[PrioritizationScore] = []
        for item in results:
            if isinstance(item, PrioritizationScore):
                scored.append(item)
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored

    async def enqueue_customer(
        self,
        customer_id: int,
        *,
        organization_id: int,
        attempt_number: int = 1,
        workflow_run_id: int | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        org_config = await self.load_org_config(organization_id)
        self._apply_config(org_config)

        scored = await self.score_customer(customer_id, organization_id=organization_id)
        if scored is None:
            return None
        if scored.score < org_config.min_score_to_call:
            return {
                "enqueued": False,
                "reason": "below_min_score",
                "score": scored.to_dict(),
            }

        profile = await self._load_profile(customer_id, organization_id=organization_id)
        if profile is None:
            return None

        debt_ref = None
        outstanding = None
        debts = profile.get("debt_accounts") or []
        if debts:
            debt_ref = debts[0].get("account_reference")
            outstanding = debts[0].get("outstanding_balance")

        entry = PrioritizedCallEntry(
            customer_id=customer_id,
            organization_id=organization_id,
            phone_e164=str(profile["phone_e164"]),
            full_name=str(profile.get("full_name") or ""),
            score=scored.score,
            tier=scored.tier,
            preferred_locale=str(profile.get("preferred_locale") or "mixed"),
            workflow_run_id=workflow_run_id,
            debt_account_reference=debt_ref,
            outstanding_balance=outstanding,
            attempt_number=attempt_number,
        )
        ok, position = await self._queue.enqueue(entry)
        track_priority_queued(
            organization_id=organization_id,
            customer_id=customer_id,
            score=scored.score,
            queue_position=position,
            attempt_number=attempt_number,
            workflow_run_id=workflow_run_id or 0,
        )
        return {
            "enqueued": ok,
            "position": position,
            "score": scored.to_dict(),
            "entry": entry.to_dict(),
        }

    async def refresh_queue(self, organization_id: int) -> dict[str, Any]:
        """Re-score all queued customers and update ordering."""
        items = await self._queue.list_queue(organization_id, limit=500)
        updated = 0
        for item in items:
            cid = int(item["customer_id"])
            scored = await self.score_customer(
                cid, organization_id=organization_id, track_analytics=False
            )
            if scored and await self._queue.refresh_score(
                organization_id, cid, new_score=scored.score
            ):
                updated += 1
        return {"queue_depth": len(items), "updated": updated}

    async def dequeue_next(self, organization_id: int) -> dict[str, Any] | None:
        entry = await self._queue.dequeue_next(organization_id)
        if entry is None:
            return None
        return entry.to_dict()

    async def process_due_retries(self, organization_id: int) -> dict[str, Any]:
        """Move due retry entries back into the active priority queue."""
        due = await self._retry_queue.due_entries(organization_id)
        requeued = 0
        for entry, schedule in due:
            entry.attempt_number = schedule.attempt_number
            _, _ = await self._queue.enqueue(entry)
            requeued += 1
        return {"due": len(due), "requeued": requeued}

    async def record_outcome(
        self,
        customer_id: int,
        *,
        organization_id: int,
        outcome: str,
        phone_e164: str | None = None,
        attempt_number: int = 1,
        workflow_run_id: int | None = None,
        duration_s: float | None = None,
    ) -> dict[str, Any]:
        """Record call outcome in CRM and schedule retry if appropriate."""
        crm = get_customer_service()
        phone = phone_e164
        if not phone:
            profile = await self._load_profile(customer_id, organization_id=organization_id)
            phone = str(profile["phone_e164"]) if profile else ""

        await crm.record_call(
            customer_id,
            organization_id=organization_id,
            phone_e164=phone,
            call_type="outbound",
            outcome=outcome,
            workflow_run_id=workflow_run_id,
            duration_s=duration_s,
        )

        scored = await self.score_customer(
            customer_id, organization_id=organization_id, track_analytics=False
        )
        score_value = scored.score if scored else 0.0
        track_call_outcome_recorded(
            organization_id=organization_id,
            customer_id=customer_id,
            outcome=outcome,
            score=score_value,
            workflow_run_id=workflow_run_id or 0,
        )

        retry_result = None
        if scored:
            schedule = self._retry_scheduler.schedule(
                customer_id=customer_id,
                organization_id=organization_id,
                attempt_number=attempt_number,
                score=scored,
                outcome=outcome,
            )
            if schedule:
                profile = await self._load_profile(customer_id, organization_id=organization_id)
                entry = PrioritizedCallEntry(
                    customer_id=customer_id,
                    organization_id=organization_id,
                    phone_e164=phone,
                    full_name=str((profile or {}).get("full_name") or ""),
                    score=scored.score,
                    tier=scored.tier,
                    attempt_number=schedule.attempt_number,
                )
                await self._retry_queue.schedule(schedule, entry)
                track_retry_scheduled(
                    organization_id=organization_id,
                    customer_id=customer_id,
                    delay_s=schedule.delay_s,
                    attempt_number=schedule.attempt_number,
                    score=scored.score,
                    reason=schedule.reason,
                    workflow_run_id=workflow_run_id or 0,
                )
                retry_result = schedule.to_dict()

        return {
            "customer_id": customer_id,
            "outcome": outcome,
            "score": scored.to_dict() if scored else None,
            "retry": retry_result,
        }

    async def queue_snapshot(self, organization_id: int) -> dict[str, Any]:
        queue_items = await self._queue.list_queue(organization_id)
        retry_items = await self._retry_queue.list_pending(organization_id)
        depth = await self._queue.depth(organization_id)
        retry_depth = await self._retry_queue.depth(organization_id)
        batch = self._retry_scheduler.optimal_batch_size(depth)
        return {
            "queue_depth": depth,
            "retry_depth": retry_depth,
            "suggested_batch_size": batch,
            "queue": queue_items,
            "retries": retry_items,
        }

    async def _load_profile(
        self,
        customer_id: int,
        *,
        organization_id: int,
    ) -> dict[str, Any] | None:
        crm = get_customer_service()
        profile = await crm.get_profile(customer_id, organization_id=organization_id)
        return profile.to_dict() if profile else None

    def _apply_config(self, config: CallPrioritizationConfig) -> None:
        self._config = config
        self._scoring = CallPrioritizationScoringEngine(config)
        self._retry_scheduler = CallRetryScheduler(config)


_service: CallPrioritizationService | None = None


def get_call_prioritization_service() -> CallPrioritizationService:
    global _service
    if _service is None:
        _service = CallPrioritizationService()
    return _service
