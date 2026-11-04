"""SaaS control plane HTTP API for non-developer operators."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.db import db_client
from api.db.models import UserModel
from api.schemas.control_plane import (
    BusinessKnowledgeCreate,
    BusinessKnowledgeUpdate,
    BusinessToolInstallRequest,
    OrganizationSetupProfile,
    WorkflowEnvironmentPromoteRequest,
    WorkflowRollbackRequest,
)
from api.services.auth.depends import get_user
from api.services.control_plane.business_tools import (
    install_business_tool,
    list_business_tools,
)
from api.services.control_plane.knowledge import (
    KNOWLEDGE_CATEGORIES,
    serialize_entry,
)
from api.services.control_plane.setup import (
    INDUSTRIES,
    KENYA_COUNTIES,
    get_setup_profile,
    save_setup_profile,
)
from api.services.control_plane.workflows import (
    builder_catalog,
    environment_heads,
    promote_environment,
    rollback_published,
)
from api.services.tool_management import ToolManagementError

router = APIRouter(prefix="/control-plane", tags=["control-plane"])


def _org_id(user: UserModel) -> int:
    if not user.selected_organization_id:
        raise HTTPException(status_code=400, detail="No organization selected")
    return user.selected_organization_id


@router.get("/setup")
async def get_organization_setup(user: UserModel = Depends(get_user)):
    profile = await get_setup_profile(_org_id(user))
    return {
        "profile": profile.model_dump(),
        "completeness": profile.completeness(),
        "counties": KENYA_COUNTIES,
        "industries": INDUSTRIES,
    }


@router.put("/setup")
async def put_organization_setup(
    body: OrganizationSetupProfile,
    user: UserModel = Depends(get_user),
):
    profile = await save_setup_profile(
        _org_id(user), body, actor_user_id=user.id
    )
    return {"profile": profile.model_dump(), "completeness": profile.completeness()}


@router.get("/knowledge")
async def list_knowledge(
    category: str | None = None,
    user: UserModel = Depends(get_user),
):
    rows = await db_client.list_business_knowledge_entries(
        _org_id(user), category=category
    )
    return {
        "categories": list(KNOWLEDGE_CATEGORIES),
        "entries": [serialize_entry(row) for row in rows],
    }


@router.post("/knowledge")
async def create_knowledge(
    body: BusinessKnowledgeCreate,
    user: UserModel = Depends(get_user),
):
    if body.category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown knowledge category")
    row = await db_client.create_business_knowledge_entry(
        organization_id=_org_id(user),
        category=body.category,
        title=body.title,
        content=body.content,
        metadata_json=body.metadata,
        document_uuid=body.document_uuid,
        created_by_user_id=user.id,
    )
    return serialize_entry(row)


@router.patch("/knowledge/{entry_id}")
async def update_knowledge(
    entry_id: int,
    body: BusinessKnowledgeUpdate,
    user: UserModel = Depends(get_user),
):
    payload = body.model_dump(exclude_unset=True)
    if "metadata" in payload:
        payload["metadata_json"] = payload.pop("metadata")
    row = await db_client.update_business_knowledge_entry(
        _org_id(user),
        entry_id,
        **payload,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return serialize_entry(row)


@router.get("/knowledge/search")
async def search_knowledge(
    q: str = Query(..., min_length=1),
    user: UserModel = Depends(get_user),
):
    from api.services.control_plane.knowledge import retrieve_relevant_knowledge

    hits = await retrieve_relevant_knowledge(_org_id(user), q)
    return {"query": q, "results": hits, "total_results": len(hits)}


@router.get("/business-tools")
async def get_business_tools(user: UserModel = Depends(get_user)):
    _ = _org_id(user)
    return {"tools": list_business_tools()}


@router.post("/business-tools/install")
async def post_install_business_tool(
    body: BusinessToolInstallRequest,
    user: UserModel = Depends(get_user),
):
    _ = _org_id(user)
    try:
        return await install_business_tool(
            user=user,
            key=body.key,
            endpoint_url=body.endpoint_url,
            transfer_destination=body.transfer_destination,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ToolManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/workflow-builder")
async def get_workflow_builder(user: UserModel = Depends(get_user)):
    _ = _org_id(user)
    return builder_catalog()


@router.get("/workflows/{workflow_id}/environments")
async def get_workflow_environments(
    workflow_id: int,
    user: UserModel = Depends(get_user),
):
    workflow = await db_client.get_workflow(
        workflow_id, organization_id=_org_id(user)
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return await environment_heads(workflow_id)


@router.post("/workflows/{workflow_id}/promote")
async def post_promote_workflow(
    workflow_id: int,
    body: WorkflowEnvironmentPromoteRequest,
    user: UserModel = Depends(get_user),
):
    workflow = await db_client.get_workflow(
        workflow_id, organization_id=_org_id(user)
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        return await promote_environment(
            workflow_id,
            body.target,
            organization_id=_org_id(user),
            user_id=user.id,
            changelog=body.changelog,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/rollback")
async def post_rollback_workflow(
    workflow_id: int,
    body: WorkflowRollbackRequest,
    user: UserModel = Depends(get_user),
):
    workflow = await db_client.get_workflow(
        workflow_id, organization_id=_org_id(user)
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        return await rollback_published(
            workflow_id,
            body.definition_id,
            organization_id=_org_id(user),
            user_id=user.id,
            changelog=body.changelog,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit-logs")
async def get_audit_logs(
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserModel = Depends(get_user),
):
    rows = await db_client.list_organization_audit_logs(
        _org_id(user), action=action, limit=limit, offset=offset
    )
    return {
        "items": [
            {
                "id": row.id,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "summary": row.summary,
                "metadata": row.metadata_json,
                "actor_user_id": row.actor_user_id,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }
