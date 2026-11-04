"""Multi-tenant usage billing and invoicing facade."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from api.constants import TENANT_USAGE_BILLING_ENABLED
from api.db.models import MpesaTransactionModel, TenantInvoiceModel, WhatsAppMessageModel
from api.services.tenant_billing.collectors import get_tenant_usage_collector
from api.services.tenant_billing.invoicing import get_tenant_invoice_generator
from api.services.tenant_billing.ledger import get_usage_ledger
from api.services.tenant_billing.plan import load_billing_plan, save_billing_plan
from api.services.tenant_billing.quota import get_tenant_quota_enforcer
from api.services.tenant_billing.schema import TenantBillingPlanSchema
from api.services.tenant_billing.types import UsageMetric


class TenantBillingService:
    @property
    def enabled(self) -> bool:
        return TENANT_USAGE_BILLING_ENABLED

    async def get_plan(self, organization_id: int) -> TenantBillingPlanSchema:
        return await load_billing_plan(organization_id)

    async def update_plan(
        self, organization_id: int, plan: TenantBillingPlanSchema
    ) -> TenantBillingPlanSchema:
        return await save_billing_plan(organization_id, plan)

    async def usage_summary(
        self,
        organization_id: int,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> dict[str, Any]:
        end = to_ts or datetime.now(UTC)
        start = from_ts or end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return await get_usage_ledger().usage_summary(
            organization_id, from_ts=start, to_ts=end
        )

    async def list_usage_events(
        self,
        organization_id: int,
        *,
        metric_code: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        from api.db import db_client

        rows, total = await db_client.list_usage_events(
            organization_id,
            metric_code=metric_code,
            limit=limit,
            offset=offset,
        )
        return {
            "organization_id": organization_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "events": [
                {
                    "id": e.id,
                    "metric_code": e.metric_code,
                    "quantity": e.quantity,
                    "unit": e.unit,
                    "billable_amount": e.billable_amount,
                    "unit_cost": getattr(e, "unit_cost", None),
                    "billing_period": getattr(e, "billing_period", None),
                    "currency": e.currency,
                    "workflow_run_id": e.workflow_run_id,
                    "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
                    "metadata": e.metadata_json or {},
                }
                for e in rows
            ],
        }

    async def list_quotas(self, organization_id: int) -> list[dict[str, Any]]:
        return await get_tenant_quota_enforcer().list_quotas(organization_id)

    async def upsert_quota(self, organization_id: int, **kwargs) -> dict[str, Any]:
        return await get_tenant_quota_enforcer().upsert_quota(organization_id, **kwargs)

    async def check_call_quota(self, organization_id: int) -> dict[str, Any]:
        outcome = await get_tenant_quota_enforcer().check(
            organization_id, UsageMetric.CALL_MINUTES, delta=1.0
        )
        return {
            "allowed": outcome.allowed,
            "metric_code": outcome.metric_code,
            "used": outcome.used,
            "limit": outcome.limit,
            "enforcement": outcome.enforcement,
            "message": outcome.error_message,
        }

    async def generate_invoice(
        self, organization_id: int, *, issue: bool = False, **period_kwargs
    ) -> TenantInvoiceModel:
        return await get_tenant_invoice_generator().generate(
            organization_id, issue=issue, **period_kwargs
        )

    async def list_invoices(
        self, organization_id: int, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[TenantInvoiceModel], int]:
        return await get_tenant_invoice_generator().list_invoices(
            organization_id, limit=limit, offset=offset
        )

    async def get_invoice(
        self, organization_id: int, invoice_id: int
    ) -> TenantInvoiceModel | None:
        return await get_tenant_invoice_generator().get_invoice(
            organization_id, invoice_id
        )

    async def issue_invoice(
        self, organization_id: int, invoice_id: int
    ) -> TenantInvoiceModel | None:
        return await get_tenant_invoice_generator().issue_invoice(
            organization_id, invoice_id
        )

    async def collect_workflow_run(self, workflow_run_id: int) -> bool:
        return await get_tenant_usage_collector().collect_workflow_run(workflow_run_id)

    async def collect_whatsapp_message(
        self, *, organization_id: int, message: WhatsAppMessageModel
    ) -> bool:
        return await get_tenant_usage_collector().collect_whatsapp_message(
            organization_id=organization_id, message=message
        )

    async def collect_mpesa_transaction(self, tx: MpesaTransactionModel) -> bool:
        return await get_tenant_usage_collector().collect_mpesa_transaction(tx)


_service: TenantBillingService | None = None


def get_tenant_billing_service() -> TenantBillingService:
    global _service
    if _service is None:
        _service = TenantBillingService()
    return _service
