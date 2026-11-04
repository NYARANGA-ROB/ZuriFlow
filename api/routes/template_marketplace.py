"""Template marketplace API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import TEMPLATE_MARKETPLACE_ENABLED
from api.db.models import UserModel
from api.schemas.template_marketplace import (
    InstallTemplateRequest,
    InstallTemplateResponse,
    MarketplaceStatusSchema,
    TemplateDetailSchema,
    TemplateSearchParams,
    TemplateSummarySchema,
    TemplateVersionSchema,
    TenantCustomizationSchema,
)
from api.services.auth.depends import get_user_with_selected_organization
from api.services.template_marketplace.catalog import list_categories, list_tags, search_templates
from api.services.template_marketplace.customization import get_template_customization_engine
from api.services.template_marketplace.install import get_template_install_service
from api.services.template_marketplace.registry import get_template_marketplace_registry
from api.services.template_marketplace.schema import TemplateSearchQuery, TenantTemplateCustomization
from api.services.tenant import TenantContext, get_tenant_context, scoped_organization_id

router = APIRouter(prefix="/template-marketplace", tags=["template-marketplace"])


def _require_enabled() -> None:
    if not TEMPLATE_MARKETPLACE_ENABLED:
        raise HTTPException(status_code=503, detail="Template marketplace is disabled")


@router.get("/status", response_model=MarketplaceStatusSchema)
async def marketplace_status(
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    registry = get_template_marketplace_registry()
    return MarketplaceStatusSchema(
        enabled=True,
        template_count=len(registry.list_listings()),
        categories=list_categories(),
        tags=list_tags(),
    )


@router.get("/listings", response_model=list[TemplateSummarySchema])
async def list_listings(
    q: str = "",
    industry: str | None = None,
    tag: str | None = None,
    category: str | None = None,
    locale: str | None = None,
    featured_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)] = None,
):
    _require_enabled()
    query = TemplateSearchQuery(
        q=q,
        industry=industry,
        tag=tag,
        category=category,
        locale=locale,
        featured_only=featured_only,
        limit=limit,
    )
    return [TemplateSummarySchema(**row) for row in search_templates(query)]


@router.get("/templates/{template_id}", response_model=TemplateDetailSchema)
async def get_template_detail(
    template_id: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    organization_id: int | None = None,
):
    _require_enabled()
    registry = get_template_marketplace_registry()
    try:
        listing = registry.require_listing(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found") from None

    org_id = scoped_organization_id(ctx, organization_id)
    detail = listing.to_detail_dict()
    if org_id:
        customization = await get_template_customization_engine().get_customization(
            org_id, template_id
        )
        detail["tenant_customization"] = customization.to_dict()
    return TemplateDetailSchema(**detail)


@router.get("/templates/{template_id}/versions", response_model=list[TemplateVersionSchema])
async def list_template_versions(
    template_id: str,
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    registry = get_template_marketplace_registry()
    try:
        versions = registry.list_versions(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found") from None
    return [TemplateVersionSchema(**v.to_dict()) for v in versions]


@router.get("/templates/{template_id}/versions/{version}")
async def get_template_version(
    template_id: str,
    version: str,
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    registry = get_template_marketplace_registry()
    try:
        tpl = registry.require_version(template_id, version)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template version not found") from None
    return tpl.to_dict()


@router.get("/templates/{template_id}/resolved")
async def get_resolved_template(
    template_id: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    organization_id: int | None = None,
    version: str | None = None,
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    engine = get_template_customization_engine()
    try:
        resolved = await engine.resolve(template_id, organization_id=org_id, version=version)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found") from None
    return resolved.to_dict()


@router.get(
    "/organizations/{organization_id}/customizations/{template_id}",
    response_model=TenantCustomizationSchema,
)
async def get_tenant_customization(
    organization_id: int,
    template_id: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    custom = await get_template_customization_engine().get_customization(org_id, template_id)
    return TenantCustomizationSchema(template_id=template_id, **custom.to_dict())


@router.put(
    "/organizations/{organization_id}/customizations/{template_id}",
    response_model=TenantCustomizationSchema,
)
async def upsert_tenant_customization(
    organization_id: int,
    template_id: str,
    body: TenantCustomizationSchema,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    get_template_marketplace_registry().require_listing(template_id)
    customization = TenantTemplateCustomization(
        template_id=template_id,
        pinned_version=body.pinned_version,
        default_locale=body.default_locale,
        metadata=body.metadata,
        global_rules=body.global_rules,
        steps=body.steps,
        prompt_overrides=body.prompt_overrides,
    )
    saved = await get_template_customization_engine().save_customization(org_id, customization)
    return TenantCustomizationSchema(template_id=template_id, **saved.to_dict())


@router.post("/templates/{template_id}/install", response_model=InstallTemplateResponse)
async def install_template(
    template_id: str,
    body: InstallTemplateRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, body.organization_id or user.selected_organization_id)
    if org_id is None:
        raise HTTPException(status_code=400, detail="No organization selected")

    try:
        result = await get_template_install_service().install(
            template_id=template_id,
            workflow_name=body.workflow_name,
            user_id=user.id,
            organization_id=org_id,
            version=body.version,
            call_direction=body.call_direction,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found") from None
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return InstallTemplateResponse(**result)
