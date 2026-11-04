"""Core usage recording and pricing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from api.constants import TENANT_BILLING_DEFAULT_CURRENCY, TENANT_USAGE_BILLING_ENABLED
from api.db import db_client
from api.services.tenant_billing.plan import load_billing_plan
from api.services.tenant_billing.types import METRIC_UNITS, UsageMetric, UsageRecordRequest


class UsageLedger:
    """Persist metered usage events with idempotent aggregation keys."""

    async def record(self, request: UsageRecordRequest) -> bool:
        if not TENANT_USAGE_BILLING_ENABLED:
            return False

        plan = await load_billing_plan(request.organization_id)
        amount = self._price(request.metric, request.quantity, plan.rates)
        unit = METRIC_UNITS[request.metric]
        unit_cost = self._unit_cost(request.metric, plan.rates)
        period = request.billing_period or datetime.now(UTC).strftime("%Y-%m")

        try:
            event = await db_client.record_usage_event(
                organization_id=request.organization_id,
                metric_code=request.metric.value,
                quantity=request.quantity,
                unit=unit,
                aggregation_key=request.aggregation_key,
                recorded_at=datetime.now(UTC),
                billable_amount=amount,
                unit_cost=request.unit_cost if request.unit_cost is not None else unit_cost,
                billing_period=period,
                currency=plan.currency or TENANT_BILLING_DEFAULT_CURRENCY,
                workflow_run_id=request.workflow_run_id,
                reference_type=request.reference_type,
                reference_id=request.reference_id,
                metadata=request.metadata,
            )
            return event is not None
        except Exception as e:
            logger.warning(
                "Failed to record usage org={} metric={}: {}",
                request.organization_id,
                request.metric.value,
                e,
            )
            return False

    @staticmethod
    def _unit_cost(metric: UsageMetric, rates) -> float:
        if metric == UsageMetric.CALL_MINUTES:
            return rates.per_minute_usd
        if metric == UsageMetric.PHONE_CALLS:
            return rates.per_phone_call_usd
        if metric == UsageMetric.WEB_CALLS:
            return rates.per_web_call_usd
        if metric == UsageMetric.STT_SECONDS:
            return rates.stt_per_minute_usd / 60.0
        if metric == UsageMetric.TTS_CHARACTERS:
            return rates.tts_per_1k_chars_usd / 1000.0
        if metric == UsageMetric.LLM_TOKENS:
            return rates.llm_per_1k_tokens_usd / 1000.0
        if metric == UsageMetric.SMS:
            return rates.sms_per_message_usd
        if metric in {UsageMetric.WHATSAPP_INBOUND, UsageMetric.WHATSAPP_OUTBOUND}:
            return rates.whatsapp_per_message_usd
        if metric == UsageMetric.MPESA_TRANSACTION:
            return rates.mpesa_per_transaction_usd
        if metric == UsageMetric.STORAGE_GB:
            return rates.storage_per_gb_usd
        return 0.0

    @staticmethod
    def _price(metric: UsageMetric, quantity: float, rates) -> float:
        unit = UsageLedger._unit_cost(metric, rates)
        if metric == UsageMetric.MPESA_COLLECTED:
            return 0.0
        return round(quantity * unit, 6)

    async def usage_summary(
        self,
        organization_id: int,
        *,
        from_ts: datetime,
        to_ts: datetime,
    ) -> dict[str, Any]:
        plan = await load_billing_plan(organization_id)
        metrics = await db_client.aggregate_usage_by_metric(
            organization_id, from_ts=from_ts, to_ts=to_ts
        )
        total = sum(m.get("total_amount", 0.0) for m in metrics.values())
        return {
            "organization_id": organization_id,
            "from_ts": from_ts.isoformat(),
            "to_ts": to_ts.isoformat(),
            "metrics": metrics,
            "total_billable_amount": round(total, 4),
            "currency": plan.currency,
        }


_ledger: UsageLedger | None = None


def get_usage_ledger() -> UsageLedger:
    global _ledger
    if _ledger is None:
        _ledger = UsageLedger()
    return _ledger
