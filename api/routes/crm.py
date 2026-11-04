"""CRM API routes for customer profiles and history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.db.models import UserModel
from api.schemas.crm import (
    AuditLogSchema,
    CreateCustomerRequest,
    CustomerProfileSchema,
    CustomerSummarySchema,
    RecordCallRequest,
    RecordEscalationRequest,
    RecordPaymentRequest,
    UpdateCustomerRequest,
    UpsertDebtAccountRequest,
)
from api.services.auth.depends import get_user
from api.services.crm.service import get_customer_service
from api.services.tenant import get_tenant_context
from api.services.tenant.types import TenantContext

router = APIRouter(prefix="/crm", tags=["crm"])


async def get_organization_id(ctx: TenantContext = Depends(get_tenant_context)) -> int:
    return ctx.organization_id


def _profile_schema(profile) -> CustomerProfileSchema:
    return CustomerProfileSchema(**profile.to_dict())


@router.get("/status")
async def crm_status(_user=Depends(get_user)):
    svc = get_customer_service()
    return {"enabled": svc.enabled}


@router.get("/customers", response_model=list[CustomerSummarySchema])
async def list_customers(
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    rows = await svc.list_customers(
        organization_id=organization_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return [CustomerSummarySchema(**r) for r in rows]


@router.post("/customers", response_model=CustomerProfileSchema)
async def create_customer(
    body: CreateCustomerRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="CRM is disabled")
    debt = body.debt_account.model_dump() if body.debt_account else None
    profile = await svc.create_customer(
        organization_id=organization_id,
        phone_e164=body.phone_e164,
        full_name=body.full_name,
        email=body.email,
        preferred_locale=body.preferred_locale,
        secondary_locales=body.secondary_locales,
        external_crm_id=body.external_crm_id,
        metadata=body.metadata,
        actor_user_id=user.id,
        debt_account=debt,
    )
    return _profile_schema(profile)


@router.get("/customers/by-phone/{phone_e164}", response_model=CustomerProfileSchema)
async def get_customer_by_phone(
    phone_e164: str,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    profile = await svc.get_profile_by_phone(
        organization_id=organization_id,
        phone_e164=phone_e164,
        actor_user_id=user.id,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _profile_schema(profile)


@router.get("/customers/{customer_id}", response_model=CustomerProfileSchema)
async def get_customer(
    customer_id: int,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    profile = await svc.get_profile(
        customer_id,
        organization_id=organization_id,
        actor_user_id=user.id,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _profile_schema(profile)


@router.patch("/customers/{customer_id}", response_model=CustomerProfileSchema)
async def update_customer(
    customer_id: int,
    body: UpdateCustomerRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    profile = await svc.update_customer(
        customer_id,
        organization_id=organization_id,
        actor_user_id=user.id,
        **body.model_dump(exclude_unset=True),
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _profile_schema(profile)


@router.put("/customers/{customer_id}/debt", response_model=dict)
async def upsert_debt_account(
    customer_id: int,
    body: UpsertDebtAccountRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    return await svc.upsert_debt_account(
        customer_id,
        organization_id=organization_id,
        actor_user_id=user.id,
        **body.model_dump(),
    )


@router.post("/customers/{customer_id}/payments", response_model=dict)
async def record_payment(
    customer_id: int,
    body: RecordPaymentRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    return await svc.record_payment(
        customer_id,
        organization_id=organization_id,
        actor_user_id=user.id,
        **body.model_dump(),
    )


@router.post("/customers/{customer_id}/calls", response_model=dict)
async def record_call(
    customer_id: int,
    body: RecordCallRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    return await svc.record_call(
        customer_id,
        organization_id=organization_id,
        actor_user_id=user.id,
        **body.model_dump(),
    )


@router.post("/customers/{customer_id}/escalations", response_model=dict)
async def record_escalation(
    customer_id: int,
    body: RecordEscalationRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_customer_service()
    return await svc.record_escalation(
        customer_id,
        organization_id=organization_id,
        actor_user_id=user.id,
        **body.model_dump(),
    )


@router.get("/audit-logs", response_model=list[AuditLogSchema])
async def list_audit_logs(
    customer_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_customer_service()
    rows = await svc.list_audit_logs(
        organization_id=organization_id,
        customer_id=customer_id,
        limit=limit,
    )
    return [AuditLogSchema(**r) for r in rows]
