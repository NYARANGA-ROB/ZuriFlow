"""Kenyan continuous learning API routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import KENYAN_CONTINUOUS_LEARNING_ENABLED
from api.schemas.kenyan_continuous_learning import (
    FeedbackIngestRequest,
    LearningSummarySchema,
    StartTrainingRequest,
    SubmitLabelRequest,
)
from api.services.kenyan_continuous_learning.service import get_kenyan_continuous_learning_service
from api.services.tenant.access_control import require_permission
from api.services.tenant.types import Permission, TenantContext

router = APIRouter(prefix="/kenyan-learning", tags=["kenyan-learning"])


def _enabled() -> None:
    if not KENYAN_CONTINUOUS_LEARNING_ENABLED:
        raise HTTPException(status_code=503, detail="Kenyan continuous learning is disabled")


def _read_ctx(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
) -> TenantContext:
    _enabled()
    return ctx


def _write_ctx(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
) -> TenantContext:
    _enabled()
    return ctx


def _operator_ctx(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CAMPAIGN_WRITE))],
) -> TenantContext:
    _enabled()
    return ctx


@router.get("/summary", response_model=LearningSummarySchema)
async def learning_summary(
    ctx: Annotated[TenantContext, Depends(_read_ctx)],
    days: int = Query(30, ge=1, le=180),
):
    data = await get_kenyan_continuous_learning_service().summary(
        ctx.organization_id, days=days
    )
    return LearningSummarySchema(**data)


@router.post("/feedback")
async def ingest_feedback(
    body: FeedbackIngestRequest,
    ctx: Annotated[TenantContext, Depends(_operator_ctx)],
) -> dict[str, Any]:
    return await get_kenyan_continuous_learning_service().ingest_feedback(
        organization_id=ctx.organization_id,
        feedback_type=body.feedback_type,
        payload=body.payload,
        user_id=ctx.user_id,
    )


@router.get("/labels")
async def list_labels(
    ctx: Annotated[TenantContext, Depends(_operator_ctx)],
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await get_kenyan_continuous_learning_service().list_label_tasks(
        ctx.organization_id, status=status, limit=limit, offset=offset
    )


@router.post("/labels/{task_id}")
async def submit_label(
    task_id: int,
    body: SubmitLabelRequest,
    ctx: Annotated[TenantContext, Depends(_operator_ctx)],
):
    from api.services.kenyan_continuous_learning.types import LabelTaskStatus

    try:
        status = LabelTaskStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid label status")
    result = await get_kenyan_continuous_learning_service().submit_label(
        organization_id=ctx.organization_id,
        task_id=task_id,
        label_payload=body.label_payload,
        status=status,
        notes=body.notes,
        user_id=ctx.user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Label task not found")
    return result


@router.post("/collect/{workflow_run_id}")
async def collect_run(
    workflow_run_id: int,
    ctx: Annotated[TenantContext, Depends(_write_ctx)],
):
    result = await get_kenyan_continuous_learning_service().collect_run(
        workflow_run_id, organization_id=ctx.organization_id
    )
    if result.get("not_found"):
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return result


@router.post("/training/start")
async def start_training(
    body: StartTrainingRequest,
    ctx: Annotated[TenantContext, Depends(_write_ctx)],
):
    return await get_kenyan_continuous_learning_service().start_training(
        ctx.organization_id,
        targets=body.targets,
        days=body.days,
        auto_apply=body.auto_apply,
    )


@router.post("/training/{run_id}/apply")
async def apply_training(
    run_id: int,
    ctx: Annotated[TenantContext, Depends(_write_ctx)],
):
    return await get_kenyan_continuous_learning_service().apply_training_run(
        ctx.organization_id, run_id
    )
