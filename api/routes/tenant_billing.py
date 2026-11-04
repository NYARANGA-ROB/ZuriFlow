"""Tenant usage billing and invoicing API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import TENANT_USAGE_BILLING_ENABLED
from api.schemas.tenant_billing import (
    GenerateInvoiceRequest,
    InvoiceSchema,
    QuotaSchema,
    TenantBillingPlanSchema,
    UpdateSubscriptionRequest,
    UpsertQuotaRequest,
    UsageSummarySchema,
)
from api.services.tenant.access_control import require_permission
from api.services.tenant.types import Permission, TenantContext
from api.services.tenant_billing.schema import (
    InvoiceLineSchema,
    TenantBillingPlanSchema as InternalPlanSchema,
)
from api.services.tenant_billing.service import get_tenant_billing_service

router = APIRouter(prefix="/tenant-billing", tags=["tenant-billing"])


def _require_enabled() -> None:
    if not TENANT_USAGE_BILLING_ENABLED:
        raise HTTPException(status_code=503, detail="Tenant usage billing is disabled")


def _billing_read(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.BILLING_READ))],
) -> TenantContext:
    _require_enabled()
    return ctx


def _billing_write(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.BILLING_WRITE))],
) -> TenantContext:
    _require_enabled()
    return ctx


def _invoice_to_schema(invoice) -> InvoiceSchema:
    return InvoiceSchema(
        id=invoice.id,
        organization_id=invoice.organization_id,
        invoice_number=invoice.invoice_number,
        period_start=invoice.period_start.isoformat(),
        period_end=invoice.period_end.isoformat(),
        status=invoice.status,
        currency=invoice.currency,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        issued_at=invoice.issued_at.isoformat() if invoice.issued_at else None,
        line_items=[
            InvoiceLineSchema(
                metric_code=line.metric_code,
                description=line.description,
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                amount=line.amount,
            )
            for line in (invoice.line_items or [])
        ],
    )


@router.get("/plans")
async def list_plan_catalog(
    ctx: Annotated[TenantContext, Depends(_billing_read)],
) -> dict[str, Any]:
    from api.services.tenant_billing.catalog import catalog_public

    return {"plans": catalog_public(), "organization_id": ctx.organization_id}


@router.get("/plan", response_model=TenantBillingPlanSchema)
async def get_billing_plan(ctx: Annotated[TenantContext, Depends(_billing_read)]):
    plan = await get_tenant_billing_service().get_plan(ctx.organization_id)
    return TenantBillingPlanSchema.model_validate(plan.model_dump())


@router.put("/plan", response_model=TenantBillingPlanSchema)
async def update_billing_plan(
    body: TenantBillingPlanSchema,
    ctx: Annotated[TenantContext, Depends(_billing_write)],
):
    plan = await get_tenant_billing_service().update_plan(
        ctx.organization_id, InternalPlanSchema.model_validate(body.model_dump())
    )
    return TenantBillingPlanSchema.model_validate(plan.model_dump())


@router.patch("/subscription")
async def update_subscription(
    body: UpdateSubscriptionRequest,
    ctx: Annotated[TenantContext, Depends(_billing_write)],
) -> dict[str, Any]:
    svc = get_tenant_billing_service()
    plan = await svc.get_plan(ctx.organization_id)
    plan.subscription.status = body.status
    if body.tier:
        plan.subscription.tier = body.tier
    await svc.update_plan(ctx.organization_id, plan)
    return {"subscription_status": plan.subscription.status.value}


@router.get("/usage/summary", response_model=UsageSummarySchema)
async def usage_summary(
    ctx: Annotated[TenantContext, Depends(_billing_read)],
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
):
    data = await get_tenant_billing_service().usage_summary(
        ctx.organization_id, from_ts=from_ts, to_ts=to_ts
    )
    return UsageSummarySchema(**data)


@router.get("/usage/events")
async def list_usage_events(
    ctx: Annotated[TenantContext, Depends(_billing_read)],
    metric_code: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    return await get_tenant_billing_service().list_usage_events(
        ctx.organization_id,
        metric_code=metric_code,
        limit=limit,
        offset=offset,
    )


@router.get("/quotas", response_model=List[QuotaSchema])
async def list_quotas(ctx: Annotated[TenantContext, Depends(_billing_read)]):
    rows = await get_tenant_billing_service().list_quotas(ctx.organization_id)
    return [QuotaSchema(**row) for row in rows]


@router.put("/quotas", response_model=QuotaSchema)
async def upsert_quota(
    body: UpsertQuotaRequest,
    ctx: Annotated[TenantContext, Depends(_billing_write)],
):
    row = await get_tenant_billing_service().upsert_quota(
        ctx.organization_id,
        metric_code=body.metric_code.value,
        limit_quantity=body.limit_quantity,
        period=body.period,
        enforcement=body.enforcement,
    )
    return QuotaSchema(**row)


@router.get("/quotas/check")
async def check_call_quota(ctx: Annotated[TenantContext, Depends(_billing_read)]):
    return await get_tenant_billing_service().check_call_quota(ctx.organization_id)


@router.get("/invoices", response_model=List[InvoiceSchema])
async def list_invoices(
    ctx: Annotated[TenantContext, Depends(_billing_read)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    invoices, _ = await get_tenant_billing_service().list_invoices(
        ctx.organization_id, limit=limit, offset=offset
    )
    return [_invoice_to_schema(inv) for inv in invoices]


@router.post("/invoices/generate", response_model=InvoiceSchema)
async def generate_invoice(
    body: GenerateInvoiceRequest,
    ctx: Annotated[TenantContext, Depends(_billing_write)],
):
    period_start = (
        datetime.fromisoformat(body.period_start) if body.period_start else None
    )
    period_end = datetime.fromisoformat(body.period_end) if body.period_end else None
    invoice = await get_tenant_billing_service().generate_invoice(
        ctx.organization_id,
        period_start=period_start,
        period_end=period_end,
        issue=body.issue,
    )
    full = await get_tenant_billing_service().get_invoice(
        ctx.organization_id, invoice.id
    )
    return _invoice_to_schema(full or invoice)


@router.get("/invoices/{invoice_id}", response_model=InvoiceSchema)
async def get_invoice(
    invoice_id: int,
    ctx: Annotated[TenantContext, Depends(_billing_read)],
):
    invoice = await get_tenant_billing_service().get_invoice(
        ctx.organization_id, invoice_id
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_schema(invoice)


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceSchema)
async def issue_invoice(
    invoice_id: int,
    ctx: Annotated[TenantContext, Depends(_billing_write)],
):
    invoice = await get_tenant_billing_service().issue_invoice(
        ctx.organization_id, invoice_id
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    full = await get_tenant_billing_service().get_invoice(
        ctx.organization_id, invoice_id
    )
    return _invoice_to_schema(full or invoice)
