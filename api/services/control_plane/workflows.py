"""Reusable graph nodes, templates, variables, and environment promotion."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.db.models import WorkflowDefinitionModel
from api.services.control_plane.audit import AGENT_PUBLISHED, WORKFLOW_CHANGED, log_admin_action

ENV_ORDER = ("draft", "testing", "staging", "published")
PRODUCTION = "published"

NODE_LIBRARY = [
    {
        "key": "collect_phone",
        "label": "Collect Kenyan phone",
        "type": "agentNode",
        "prompt": "Ask for the customer's Safaricom or Airtel number and confirm it.",
    },
    {
        "key": "confirm_kes",
        "label": "Confirm amount in KES",
        "type": "agentNode",
        "prompt": "Repeat the amount in Kenya Shillings and wait for confirmation.",
    },
    {
        "key": "offer_mpesa",
        "label": "Offer M-Pesa",
        "type": "agentNode",
        "prompt": "Offer STK push or paybill payment and explain the next step.",
    },
    {
        "key": "escalate_human",
        "label": "Escalate to human",
        "type": "transferCall",
        "prompt": "Transfer to the on-call supervisor if the customer asks for a person.",
    },
]

WORKFLOW_TEMPLATES = [
    {
        "key": "missed_call_followup",
        "name": "Missed-call follow-up",
        "description": "Greet, identify the customer, and offer a callback or WhatsApp.",
    },
    {
        "key": "payment_reminder",
        "name": "Payment reminder",
        "description": "Confirm balance, offer M-Pesa, and schedule a retry if needed.",
    },
    {
        "key": "appointment_confirm",
        "name": "Appointment confirmation",
        "description": "Confirm date, location, and send an SMS summary.",
    },
]

VARIABLE_CATALOG = [
    {"name": "customer_name", "description": "Name from CRM or the current call"},
    {"name": "customer_phone", "description": "Normalized Kenyan phone number"},
    {"name": "amount_kes", "description": "Outstanding or quoted amount in KES"},
    {"name": "branch_name", "description": "Store or branch from business knowledge"},
    {"name": "language", "description": "en, sw, or mixed"},
]


def builder_catalog() -> dict[str, Any]:
    return {
        "reusable_nodes": NODE_LIBRARY,
        "templates": WORKFLOW_TEMPLATES,
        "variables": VARIABLE_CATALOG,
        "environments": list(ENV_ORDER),
        "production_environment": PRODUCTION,
    }


async def environment_heads(workflow_id: int) -> dict[str, Any]:
    versions = await db_client.get_workflow_versions(workflow_id)
    heads: dict[str, Any] = {env: None for env in ENV_ORDER}
    for version in versions:
        status = version.status
        if status in heads and heads[status] is None:
            heads[status] = {
                "id": version.id,
                "version_number": version.version_number,
                "changelog": getattr(version, "changelog", None),
                "published_at": version.published_at,
                "created_at": version.created_at,
                "created_by_user_id": getattr(version, "created_by_user_id", None),
                "published_by_user_id": getattr(version, "published_by_user_id", None),
            }
    return {"environments": heads, "can_publish_to_production": heads["staging"] is not None}


async def _upsert_status_snapshot(
    workflow_id: int,
    status: str,
    source: WorkflowDefinitionModel,
    *,
    changelog: str | None,
    user_id: int | None,
) -> WorkflowDefinitionModel:
    async with db_client.async_session() as session:
        from sqlalchemy import select

        from api.db.models import WorkflowDefinitionModel as Def

        existing = (
            await session.execute(
                select(Def).where(Def.workflow_id == workflow_id, Def.status == status)
            )
        ).scalars().first()
        if existing:
            existing.workflow_json = source.workflow_json
            existing.workflow_configurations = source.workflow_configurations
            existing.template_context_variables = source.template_context_variables
            existing.changelog = changelog
            existing.created_by_user_id = user_id
            row = existing
        else:
            next_version = await db_client._next_version_number(session, workflow_id)
            row = Def(
                workflow_id=workflow_id,
                workflow_json=source.workflow_json,
                workflow_configurations=source.workflow_configurations,
                template_context_variables=source.template_context_variables,
                status=status,
                version_number=next_version,
                is_current=False,
                changelog=changelog,
                created_by_user_id=user_id,
            )
            session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def promote_environment(
    workflow_id: int,
    target: str,
    *,
    organization_id: int,
    user_id: int,
    changelog: str | None = None,
) -> dict[str, Any]:
    if target not in ("testing", "staging", "published"):
        raise ValueError("target must be testing, staging, or published")

    versions = await db_client.get_workflow_versions(workflow_id)
    by_status = {}
    for version in versions:
        by_status.setdefault(version.status, version)

    if target == "testing":
        source = by_status.get("draft")
        if source is None:
            raise ValueError("A draft workflow is required before testing")
    elif target == "staging":
        source = by_status.get("testing")
        if source is None:
            raise ValueError("Promote to testing before staging")
    else:
        source = by_status.get("staging")
        if source is None:
            raise ValueError(
                "Promote to staging before production. Unfinished drafts cannot go live."
            )

    if target == "published":
        await db_client.save_workflow_draft(
            workflow_id,
            workflow_definition=source.workflow_json,
            workflow_configurations=source.workflow_configurations,
            template_context_variables=source.template_context_variables,
        )
        published = await db_client.publish_workflow_draft(
            workflow_id,
            changelog=changelog or "Promoted from staging",
            published_by_user_id=user_id,
        )
        await log_admin_action(
            organization_id=organization_id,
            action=AGENT_PUBLISHED,
            resource_type="workflow",
            actor_user_id=user_id,
            resource_id=str(workflow_id),
            summary=changelog or f"Published workflow version {published.version_number}",
            metadata={"version_number": published.version_number},
        )
        return {"status": published.status, "id": published.id, "version_number": published.version_number}

    snapshot = await _upsert_status_snapshot(
        workflow_id, target, source, changelog=changelog, user_id=user_id
    )
    await log_admin_action(
        organization_id=organization_id,
        action=WORKFLOW_CHANGED,
        resource_type="workflow",
        actor_user_id=user_id,
        resource_id=str(workflow_id),
        summary=changelog or f"Promoted workflow to {target}",
        metadata={"environment": target, "version_id": snapshot.id},
    )
    return {"status": snapshot.status, "id": snapshot.id, "version_number": snapshot.version_number}


async def rollback_published(
    workflow_id: int,
    definition_id: int,
    *,
    organization_id: int,
    user_id: int,
    changelog: str | None = None,
) -> dict[str, Any]:
    versions = await db_client.get_workflow_versions(workflow_id)
    source = next((item for item in versions if item.id == definition_id), None)
    if source is None:
        raise ValueError(f"Version {definition_id} not found")
    await db_client.save_workflow_draft(
        workflow_id,
        workflow_definition=source.workflow_json,
        workflow_configurations=source.workflow_configurations,
        template_context_variables=source.template_context_variables,
    )
    published = await db_client.publish_workflow_draft(
        workflow_id,
        changelog=changelog or f"Rolled back to definition {definition_id}",
        published_by_user_id=user_id,
    )
    await log_admin_action(
        organization_id=organization_id,
        action=AGENT_PUBLISHED,
        resource_type="workflow",
        actor_user_id=user_id,
        resource_id=str(workflow_id),
        summary=published.changelog,
        metadata={
            "rolled_back_from": definition_id,
            "version_number": published.version_number,
        },
    )
    return {
        "status": published.status,
        "id": published.id,
        "version_number": published.version_number,
    }
