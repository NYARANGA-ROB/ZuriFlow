"""Automated AI conversation quality evaluation APIs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.constants import CONVERSATION_QUALITY_ENABLED
from api.schemas.conversation_quality import (
    ConversationEvaluationSchema,
    ConversationQualityStatusSchema,
    ConversationQualitySummarySchema,
)
from api.services.conversation_quality.service import get_conversation_quality_service
from api.services.tenant.access_control import require_permission
from api.services.tenant.types import Permission, TenantContext

router = APIRouter(prefix="/conversation-quality", tags=["conversation-quality"])


def _require_enabled() -> None:
    if not CONVERSATION_QUALITY_ENABLED:
        raise HTTPException(
            status_code=503, detail="Conversation quality evaluation is disabled"
        )


def _analytics_ctx(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
) -> TenantContext:
    _require_enabled()
    return ctx


@router.get("/status", response_model=ConversationQualityStatusSchema)
async def quality_status(
    _ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
):
    return ConversationQualityStatusSchema(**get_conversation_quality_service().status())


@router.post("/evaluate/{workflow_run_id}", response_model=ConversationEvaluationSchema)
async def evaluate_run(
    workflow_run_id: int,
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
):
    result = await get_conversation_quality_service().evaluate_run(workflow_run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found or not evaluable")
    if result.get("organization_id") != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return ConversationEvaluationSchema(**result)


@router.get("/runs/{workflow_run_id}", response_model=ConversationEvaluationSchema)
async def get_run_evaluation(
    workflow_run_id: int,
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
):
    result = await get_conversation_quality_service().get_evaluation(
        ctx.organization_id, workflow_run_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return ConversationEvaluationSchema(**result)


@router.get("/summary", response_model=ConversationQualitySummarySchema)
async def org_summary(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    days: int = Query(30, ge=1, le=90),
):
    data = await get_conversation_quality_service().org_summary(
        ctx.organization_id, days=days
    )
    return ConversationQualitySummarySchema(**data)


@router.get("/regressions")
async def list_regressions(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    return await get_conversation_quality_service().list_evaluations(
        ctx.organization_id,
        days=days,
        regression_only=True,
        limit=limit,
    )


@router.get("/reports/summary.csv")
async def export_summary_csv(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    days: int = Query(30, ge=1, le=90),
):
    data = await get_conversation_quality_service().list_evaluations(
        ctx.organization_id, days=days, limit=500
    )
    buf, filename = get_conversation_quality_service().export_summary_csv(
        data["evaluations"]
    )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/runs/{workflow_run_id}.json")
async def export_run_json(
    workflow_run_id: int,
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
):
    result = await get_conversation_quality_service().get_evaluation(
        ctx.organization_id, workflow_run_id
    )
    if result is None:
        result = await get_conversation_quality_service().evaluate_run(workflow_run_id)
    if result is None or result.get("organization_id") != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    buf, filename = get_conversation_quality_service().export_run_json(result)
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
