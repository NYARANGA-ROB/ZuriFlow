"""Pydantic schemas for vertical workflow APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VerticalWorkflowStatusSchema(BaseModel):
    enabled: bool
    template_count: int


class TemplateSummarySchema(BaseModel):
    template_id: str
    name: str
    industry: str
    version: str
    description: str
    supported_locales: list[str]
    integrations: dict[str, Any]


class TemplateDetailSchema(TemplateSummarySchema):
    default_locale: str
    entry_step_id: str
    steps: list[dict[str, Any]]
    global_rules: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartInstanceRequest(BaseModel):
    template_id: str
    organization_id: int
    workflow_run_id: int | None = None
    locale: str | None = None
    initial_variables: dict[str, Any] = Field(default_factory=dict)


class WorkflowEventRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EvaluateRulesRequest(BaseModel):
    rules: list[dict[str, Any]]
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResultSchema(BaseModel):
    instance_id: str
    status: str
    current_step_id: str
    actions_taken: list[dict[str, Any]]
    variables: dict[str, Any]
    prompt: str
    escalated: bool
    payment_requested: bool


class InstanceDetailSchema(BaseModel):
    instance_id: str
    template_id: str
    organization_id: int
    workflow_run_id: int | None
    status: str
    current_step_id: str
    locale: str
    variables: dict[str, Any]
    history: list[dict[str, Any]]
    created_at: float
    updated_at: float


class EvaluateRulesResponse(BaseModel):
    matched_rule_ids: list[str]
    actions: list[dict[str, Any]]
