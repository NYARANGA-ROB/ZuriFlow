"""Automated evaluation of voice agents against synthetic and gated production samples."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from api.constants import AGENT_EVAL_ENABLED
from api.schemas.agent_eval import (
    AgentEvalStatusSchema,
    RunSuiteRequest,
    SampleProductionRequest,
    TrainingGovernanceRequest,
)
from api.services.agent_eval.service import get_agent_eval_service
from api.services.tenant.access_control import require_permission
from api.services.tenant.types import Permission, TenantContext

router = APIRouter(prefix="/agent-eval", tags=["agent-eval"])


def _ctx_read(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
) -> TenantContext:
    if not AGENT_EVAL_ENABLED:
        raise HTTPException(status_code=503, detail="Agent evaluation is disabled")
    return ctx


def _ctx_write(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.WORKFLOW_READ))],
) -> TenantContext:
    if not AGENT_EVAL_ENABLED:
        raise HTTPException(status_code=503, detail="Agent evaluation is disabled")
    ctx.require_permission(Permission.WORKFLOW_EXECUTE)
    return ctx


@router.get("/status", response_model=AgentEvalStatusSchema)
async def eval_status(
    _ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
):
    return AgentEvalStatusSchema(**get_agent_eval_service().status())


@router.get("/scenarios")
async def list_scenarios(ctx: Annotated[TenantContext, Depends(_ctx_read)]) -> dict[str, Any]:
    return {"scenarios": get_agent_eval_service().list_scenarios()}


@router.post("/runs")
async def run_suite(
    body: RunSuiteRequest,
    ctx: Annotated[TenantContext, Depends(_ctx_write)],
) -> dict[str, Any]:
    try:
        return await get_agent_eval_service().run_suite(
            organization_id=ctx.organization_id,
            workflow_id=body.workflow_id,
            scenario_ids=body.scenario_ids,
            trigger="manual",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs")
async def list_runs(
    ctx: Annotated[TenantContext, Depends(_ctx_read)],
    workflow_id: int | None = None,
) -> dict[str, Any]:
    return {
        "runs": await get_agent_eval_service().list_runs(
            ctx.organization_id, workflow_id=workflow_id
        )
    }


@router.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    ctx: Annotated[TenantContext, Depends(_ctx_read)],
) -> dict[str, Any]:
    try:
        return await get_agent_eval_service().get_run(
            run_id, organization_id=ctx.organization_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/rerun-failed")
async def rerun_failed(
    run_id: int,
    ctx: Annotated[TenantContext, Depends(_ctx_write)],
) -> dict[str, Any]:
    try:
        return await get_agent_eval_service().rerun_failed(
            run_id, organization_id=ctx.organization_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scenarios/{scenario_id}/rerun")
async def rerun_scenario(
    scenario_id: str,
    body: RunSuiteRequest,
    ctx: Annotated[TenantContext, Depends(_ctx_write)],
) -> dict[str, Any]:
    try:
        return await get_agent_eval_service().rerun_scenario(
            scenario_id,
            organization_id=ctx.organization_id,
            workflow_id=body.workflow_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/production-samples")
async def sample_production(
    body: SampleProductionRequest,
    ctx: Annotated[TenantContext, Depends(_ctx_write)],
) -> dict[str, Any]:
    ctx.require_permission(Permission.TRANSCRIPT_READ)
    try:
        return await get_agent_eval_service().sample_production_run(
            organization_id=ctx.organization_id,
            workflow_run_id=body.workflow_run_id,
            consent_ok=body.consent_ok,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/production-samples")
async def list_production_samples(
    ctx: Annotated[TenantContext, Depends(_ctx_read)],
) -> dict[str, Any]:
    return {
        "samples": await get_agent_eval_service().list_production_samples(
            ctx.organization_id
        )
    }


@router.post("/production-samples/{sample_id}/training")
async def set_training(
    sample_id: int,
    body: TrainingGovernanceRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.SECURITY_ADMIN))],
) -> dict[str, Any]:
    if not AGENT_EVAL_ENABLED:
        raise HTTPException(status_code=503, detail="Agent evaluation is disabled")
    try:
        return await get_agent_eval_service().set_training_eligible(
            sample_id,
            organization_id=ctx.organization_id,
            eligible=body.eligible,
            confirmation=body.confirmation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
