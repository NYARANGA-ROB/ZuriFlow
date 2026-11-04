"""API schemas for the template marketplace."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MarketplaceStatusSchema(BaseModel):
    enabled: bool
    template_count: int
    categories: list[str]
    tags: list[str]


class TemplateSummarySchema(BaseModel):
    template_id: str
    name: str
    industry: str
    version: str
    description: str
    default_locale: str
    supported_locales: list[str]
    integrations: dict[str, Any]
    tags: list[str]
    category: str
    featured: bool
    icon: str
    extends_template_id: str | None
    latest_version: str


class TemplateVersionSchema(BaseModel):
    version: str
    released_at: str
    changelog: str
    status: str


class TemplateDetailSchema(TemplateSummarySchema):
    template: dict[str, Any]
    version_history: list[TemplateVersionSchema]
    search_keywords: list[str]


class TemplateSearchParams(BaseModel):
    q: str = ""
    industry: str | None = None
    tag: str | None = None
    category: str | None = None
    locale: str | None = None
    featured_only: bool = False
    limit: int = Field(default=50, ge=1, le=100)


class TenantCustomizationSchema(BaseModel):
    template_id: str
    pinned_version: str | None = None
    default_locale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    global_rules: list[dict[str, Any]] = Field(default_factory=list)
    steps: dict[str, dict[str, Any]] = Field(default_factory=dict)
    prompt_overrides: dict[str, dict[str, str]] = Field(default_factory=dict)


class InstallTemplateRequest(BaseModel):
    workflow_name: str = Field(min_length=2, max_length=120)
    organization_id: int | None = None
    version: str | None = None
    call_direction: str = "inbound"


class InstallTemplateResponse(BaseModel):
    workflow_id: int
    workflow_name: str
    template_id: str
    template_version: str
