"""M-Pesa Daraja API routes and callback handlers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from api.db.models import UserModel
from api.schemas.mpesa import (
    MpesaCallbackResponse,
    MpesaTransactionSchema,
    STKPushRequestSchema,
    STKPushResponseSchema,
)
from api.services.auth.depends import get_user
from api.services.mpesa_daraja.pipeline import MpesaAsyncPipeline, STKPushService
from api.services.mpesa_daraja.types import STKPushRequest
from api.services.mpesa_daraja.webhook import validate_callback_request
from api.services.tenant import get_tenant_context
from api.services.tenant.types import TenantContext
from api.services.voice_mpesa.engine import get_voice_mpesa_engine

router = APIRouter(prefix="/mpesa", tags=["mpesa"])
_pipeline = MpesaAsyncPipeline()
_stk = STKPushService()


async def get_organization_id(ctx: TenantContext = Depends(get_tenant_context)) -> int:
    return ctx.organization_id


@router.post("/stk-push", response_model=STKPushResponseSchema)
async def initiate_stk_push(
    body: STKPushRequestSchema,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    config = await _stk.load_org_config(organization_id)
    if not config.enabled:
        raise HTTPException(status_code=403, detail="M-Pesa is disabled for this organization")

    result = await _stk.initiate_stk_push(
        STKPushRequest(
            phone_e164=body.phone_e164,
            amount=body.amount,
            account_reference=body.account_reference,
            transaction_desc=body.transaction_desc,
            organization_id=organization_id,
            workflow_run_id=body.workflow_run_id,
            metadata=body.metadata,
        )
    )
    return STKPushResponseSchema(
        success=result.success,
        transaction_id=result.transaction_id,
        merchant_request_id=result.merchant_request_id,
        checkout_request_id=result.checkout_request_id,
        customer_message=result.customer_message,
        error=result.error,
    )


@router.get("/transactions", response_model=list[MpesaTransactionSchema])
async def list_transactions(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    from api.db import db_client

    rows = await db_client.list_transactions(
        organization_id=organization_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    results = []
    for row in rows:
        detail = await _stk.get_transaction(row.id, organization_id=organization_id)
        if detail:
            results.append(MpesaTransactionSchema(**detail))
    return results


@router.get("/transactions/{transaction_id}", response_model=MpesaTransactionSchema)
async def get_transaction(
    transaction_id: int,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    detail = await _stk.get_transaction(transaction_id, organization_id=organization_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return MpesaTransactionSchema(**detail)


@router.post("/transactions/{transaction_id}/verify")
async def verify_transaction(
    transaction_id: int,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    return await _stk.verify_transaction(transaction_id, organization_id=organization_id)


@router.post("/transactions/{transaction_id}/retry", response_model=STKPushResponseSchema)
async def retry_transaction(
    transaction_id: int,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    result = await _pipeline.retry_failed_initiation(
        transaction_id,
        organization_id=organization_id,
    )
    return STKPushResponseSchema(
        success=result.success,
        transaction_id=result.transaction_id,
        merchant_request_id=result.merchant_request_id,
        checkout_request_id=result.checkout_request_id,
        customer_message=result.customer_message,
        error=result.error,
    )


@router.post("/callbacks/stk/{organization_id}", response_model=MpesaCallbackResponse)
async def stk_callback(organization_id: int, request: Request):
    """Safaricom STK Push callback endpoint (org-scoped)."""
    config_row = await _stk.load_org_config(organization_id)
    if not config_row.enabled:
        return MpesaCallbackResponse(ResultCode=0, ResultDesc="Ignored")

    payload = await validate_callback_request(
        request,
        config_row,
        organization_id=organization_id,
    )
    await _pipeline.enqueue_callback(organization_id, payload)
    return MpesaCallbackResponse()


@router.post("/callbacks/stk", response_model=MpesaCallbackResponse)
async def stk_callback_legacy(request: Request):
    """Legacy callback URL without org in path — resolves org from checkout ID."""
    from api.db import db_client
    from api.services.mpesa_daraja.webhook import parse_stk_callback

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty callback body")

    import json

    payload = json.loads(body.decode("utf-8"))
    parsed = parse_stk_callback(payload)
    tx = await db_client.get_transaction_by_checkout_request_id(parsed.checkout_request_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    config = await _stk.load_org_config(tx.organization_id)
    if config.webhook_secret:
        signature = request.headers.get("x-mpesa-signature") or request.headers.get(
            "X-Mpesa-Signature"
        )
        from api.services.mpesa_daraja.webhook import verify_hmac_signature

        if not signature or not verify_hmac_signature(body, config.webhook_secret, signature):
            raise HTTPException(status_code=401, detail="Invalid callback signature")

    await _pipeline.enqueue_callback(tx.organization_id, payload)
    return MpesaCallbackResponse()


@router.get("/voice-payment/session/{session_id}")
async def get_voice_payment_session(
    session_id: str,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    engine = get_voice_mpesa_engine()
    session = engine.get_session(session_id)
    if not session or session.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Voice payment session not found")
    return session.to_dict()


@router.post("/voice-payment/{session_id}/offer")
async def offer_voice_payment(
    session_id: str,
    amount: float | None = None,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    engine = get_voice_mpesa_engine()
    session = engine.get_session(session_id)
    if not session or session.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Voice payment session not found")
    result = await engine.offer_payment(session_id, amount=amount)
    return {
        "handled": result.handled,
        "state": result.state.value if result.state else None,
        "speak_prompt": result.speak_prompt,
    }
