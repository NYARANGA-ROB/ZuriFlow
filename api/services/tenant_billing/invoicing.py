"""Tenant invoice generation from usage events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from dateutil.relativedelta import relativedelta

from api.constants import TENANT_BILLING_DEFAULT_CURRENCY, TENANT_BILLING_TAX_RATE
from api.db import db_client
from api.db.models import TenantInvoiceModel
from api.services.tenant_billing.ledger import get_usage_ledger
from api.services.tenant_billing.plan import load_billing_plan
from api.services.tenant_billing.types import InvoiceStatus, UsageMetric

_METRIC_LABELS = {
    UsageMetric.CALL_MINUTES.value: "Voice call minutes",
    UsageMetric.PHONE_CALLS.value: "Phone calls",
    UsageMetric.WEB_CALLS.value: "Web calls",
    UsageMetric.STT_SECONDS.value: "Speech-to-text",
    UsageMetric.TTS_CHARACTERS.value: "Text-to-speech characters",
    UsageMetric.LLM_TOKENS.value: "LLM tokens",
    UsageMetric.SMS.value: "SMS messages",
    UsageMetric.WHATSAPP_INBOUND.value: "WhatsApp inbound messages",
    UsageMetric.WHATSAPP_OUTBOUND.value: "WhatsApp outbound messages",
    UsageMetric.MPESA_TRANSACTION.value: "M-Pesa transactions",
    UsageMetric.MPESA_COLLECTED.value: "M-Pesa collected (KES)",
    UsageMetric.STORAGE_GB.value: "Recording storage (GB)",
}


class TenantInvoiceGenerator:
    async def generate(
        self,
        organization_id: int,
        *,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        issue: bool = False,
    ) -> TenantInvoiceModel:
        plan = await load_billing_plan(organization_id)
        start, end = self._resolve_period(period_start, period_end)
        aggregates = await db_client.aggregate_usage_by_metric(
            organization_id, from_ts=start, to_ts=end
        )

        line_items: list[dict[str, Any]] = []
        subtotal = 0.0
        rates = plan.rates

        for metric_code, data in aggregates.items():
            quantity = float(data.get("total_quantity") or 0.0)
            if quantity <= 0:
                continue
            unit = data.get("unit") or "units"
            unit_price = self._unit_price(metric_code, rates)
            amount = float(data.get("total_amount") or 0.0)
            if amount <= 0 and unit_price > 0:
                amount = round(quantity * unit_price, 4)
            subtotal += amount
            line_items.append(
                {
                    "metric_code": metric_code,
                    "description": _METRIC_LABELS.get(metric_code, metric_code),
                    "quantity": round(quantity, 4),
                    "unit": unit,
                    "unit_price": unit_price,
                    "amount": round(amount, 4),
                    "metadata": {"event_count": data.get("event_count", 0)},
                }
            )

        tax = round(subtotal * TENANT_BILLING_TAX_RATE, 4)
        total = round(subtotal + tax, 4)
        invoice_number = await self._next_invoice_number(organization_id, start)

        status = InvoiceStatus.ISSUED.value if issue else InvoiceStatus.DRAFT.value
        invoice = await db_client.create_invoice(
            organization_id=organization_id,
            invoice_number=invoice_number,
            period_start=start,
            period_end=end,
            currency=plan.currency or TENANT_BILLING_DEFAULT_CURRENCY,
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            status=status,
            metadata={"plan_id": plan.plan_id},
            line_items=line_items,
            issued_at=datetime.now(UTC) if issue else None,
        )
        return invoice

    async def list_invoices(
        self, organization_id: int, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[TenantInvoiceModel], int]:
        return await db_client.list_invoices(
            organization_id, limit=limit, offset=offset
        )

    async def get_invoice(
        self, organization_id: int, invoice_id: int
    ) -> TenantInvoiceModel | None:
        return await db_client.get_invoice(invoice_id, organization_id=organization_id)

    async def issue_invoice(
        self, organization_id: int, invoice_id: int
    ) -> TenantInvoiceModel | None:
        return await db_client.update_invoice_status(
            invoice_id,
            organization_id=organization_id,
            status=InvoiceStatus.ISSUED.value,
            issued_at=datetime.now(UTC),
        )

    @staticmethod
    def _resolve_period(
        period_start: datetime | None,
        period_end: datetime | None,
    ) -> tuple[datetime, datetime]:
        if period_start and period_end:
            return period_start, period_end
        now = datetime.now(UTC)
        start = (now - relativedelta(months=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end = start + relativedelta(months=1)
        return start, end

    @staticmethod
    def _unit_price(metric_code: str, rates) -> float:
        from api.services.tenant_billing.ledger import UsageLedger
        from api.services.tenant_billing.types import UsageMetric as UM

        try:
            metric = UM(metric_code)
        except ValueError:
            return 0.0
        return UsageLedger._unit_cost(metric, rates)

    async def _next_invoice_number(
        self, organization_id: int, period_start: datetime
    ) -> str:
        existing, _ = await db_client.list_invoices(organization_id, limit=1, offset=0)
        seq = len(existing) + 1
        return f"INV-{organization_id}-{period_start.strftime('%Y%m')}-{seq:03d}"


_generator: TenantInvoiceGenerator | None = None


def get_tenant_invoice_generator() -> TenantInvoiceGenerator:
    global _generator
    if _generator is None:
        _generator = TenantInvoiceGenerator()
    return _generator
