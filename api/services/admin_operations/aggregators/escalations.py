"""Human escalation tracking aggregation."""

from __future__ import annotations

from typing import Any

from api.constants import CALL_RELIABILITY_ENABLED, HUMAN_ESCALATION_ENABLED
from api.services.call_reliability.service import get_call_reliability_service
from api.services.human_escalation.service import HumanEscalationService


class EscalationsAggregator:
    def __init__(self) -> None:
        self._escalation = HumanEscalationService()
        self._reliability = get_call_reliability_service()

    async def summary(
        self, organization_id: int, *, days: int = 7
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "organization_id": organization_id,
            "human_escalation_enabled": HUMAN_ESCALATION_ENABLED,
            "call_reliability_enabled": CALL_RELIABILITY_ENABLED,
        }
        if HUMAN_ESCALATION_ENABLED and self._escalation.enabled:
            result["escalation"] = await self._escalation.dashboard_summary(
                organization_id
            )
        if CALL_RELIABILITY_ENABLED and self._reliability.enabled:
            result["reliability"] = {
                "failure_summary": await self._reliability.failure_summary(
                    organization_id, days=days
                ),
                "pending_retries": await self._reliability.list_pending_retries(
                    organization_id, limit=20
                ),
            }
        return result
