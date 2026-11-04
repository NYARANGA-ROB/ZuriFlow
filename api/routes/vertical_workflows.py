"""FastAPI routes for vertical AI business-agent workflows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.schemas.vertical_workflows import (
    EvaluateRulesRequest,
    EvaluateRulesResponse,
    InstanceDetailSchema,
    StartInstanceRequest,
    TemplateDetailSchema,
    TemplateSummarySchema,
    VerticalWorkflowStatusSchema,
    WorkflowEventRequest,
    WorkflowExecutionResultSchema,
)
from api.services.auth.depends import get_user
from api.services.tenant import assert_same_tenant, scoped_organization_id
from api.services.tenant.route_helpers import TenantContextDep
from api.services.vertical_workflows.engine import get_vertical_workflow_engine
from api.services.vertical_workflows.loader import get_vertical_template_loader
from api.services.vertical_workflows.registry import get_vertical_workflow_registry
from api.services.vertical_workflows.rules import get_business_rule_engine
from api.services.vertical_workflows.schema import (
    BusinessRule,
    VerticalIndustry,
    WorkflowEvent,
    WorkflowEventType,
)

router = APIRouter(prefix="/vertical-workflows", tags=["vertical-workflows"])


def _execution_schema(result) -> WorkflowExecutionResultSchema:
    return WorkflowExecutionResultSchema(**result.to_dict())


@router.get("/status", response_model=VerticalWorkflowStatusSchema)
async def vertical_workflow_status(_user=Depends(get_user)):
    engine = get_vertical_workflow_engine()
    registry = get_vertical_workflow_registry()
    return VerticalWorkflowStatusSchema(
        enabled=engine.enabled,
        template_count=len(registry.list_templates()),
    )


@router.get("/templates", response_model=list[TemplateSummarySchema])
async def list_templates(
    industry: str | None = Query(None),
    _user=Depends(get_user),
):
    registry = get_vertical_workflow_registry()
    ind = VerticalIndustry(industry) if industry else None
    templates = registry.list_templates(industry=ind)
    return [
        TemplateSummarySchema(
            template_id=t.template_id,
            name=t.name,
            industry=t.industry.value,
            version=t.version,
            description=t.description,
            supported_locales=list(t.supported_locales),
            integrations=t.integrations.to_dict(),
        )
        for t in templates
    ]


@router.get("/templates/{template_id}", response_model=TemplateDetailSchema)
async def get_template(
    template_id: str,
    ctx: TenantContextDep,
    organization_id: int | None = Query(None),
):
    org_id = scoped_organization_id(ctx, organization_id)
    loader = get_vertical_template_loader()
    try:
        template = await loader.load(template_id, organization_id=org_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found") from None
    data = template.to_dict()
    return TemplateDetailSchema(
        template_id=data["template_id"],
        name=data["name"],
        industry=data["industry"],
        version=data["version"],
        description=data["description"],
        supported_locales=data["supported_locales"],
        integrations=data["integrations"],
        default_locale=data["default_locale"],
        entry_step_id=data["entry_step_id"],
        steps=data["steps"],
        global_rules=data["global_rules"],
        metadata=data["metadata"],
    )


@router.post("/instances", response_model=WorkflowExecutionResultSchema)
async def start_instance(body: StartInstanceRequest, ctx: TenantContextDep):
    engine = get_vertical_workflow_engine()
    if not engine.enabled:
        raise HTTPException(status_code=503, detail="Vertical workflows are disabled")
    org_id = scoped_organization_id(ctx, body.organization_id)
    try:
        result = await engine.start(
            template_id=body.template_id,
            organization_id=org_id,
            workflow_run_id=body.workflow_run_id,
            locale=body.locale,
            initial_variables=body.initial_variables,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found") from None
    return _execution_schema(result)


@router.get("/instances/{instance_id}", response_model=InstanceDetailSchema)
async def get_instance(instance_id: str, ctx: TenantContextDep):
    engine = get_vertical_workflow_engine()
    instance = await engine.get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    assert_same_tenant(ctx, instance.organization_id)
    return InstanceDetailSchema(**instance.to_dict())


@router.get("/instances/{instance_id}/prompt")
async def get_instance_prompt(
    instance_id: str,
    ctx: TenantContextDep,
    locale: str | None = Query(None),
):
    engine = get_vertical_workflow_engine()
    instance = await engine.get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    assert_same_tenant(ctx, instance.organization_id)
    try:
        prompt = await engine.get_prompt(instance_id, locale=locale)
    except KeyError:
        raise HTTPException(status_code=404, detail="Instance not found") from None
    return {"instance_id": instance_id, "prompt": prompt, "locale": locale}


@router.post("/instances/{instance_id}/events", response_model=WorkflowExecutionResultSchema)
async def process_instance_event(
    instance_id: str,
    body: WorkflowEventRequest,
    ctx: TenantContextDep,
):
    engine = get_vertical_workflow_engine()
    instance = await engine.get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    assert_same_tenant(ctx, instance.organization_id)
    try:
        event_type = WorkflowEventType(body.event_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event_type") from None
    try:
        result = await engine.process_event(
            instance_id,
            WorkflowEvent(event_type, body.payload),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Instance not found") from None
    return _execution_schema(result)


@router.post("/rules/evaluate", response_model=EvaluateRulesResponse)
async def evaluate_rules(body: EvaluateRulesRequest, _user=Depends(get_user)):
    engine = get_business_rule_engine()
    rules = tuple(BusinessRule.from_dict(r) for r in body.rules)
    matched = engine.match_rules(rules, body.context)
    actions = engine.evaluate(rules, body.context)
    return EvaluateRulesResponse(
        matched_rule_ids=[r.rule_id for r in matched],
        actions=[a.to_dict() for a in actions],
    )
