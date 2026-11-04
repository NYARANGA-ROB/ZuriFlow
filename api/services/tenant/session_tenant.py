"""Resolve and enforce tenant ownership for session-scoped API routes."""

from __future__ import annotations

import json
import time

import redis.asyncio as aioredis
from fastapi import HTTPException

from api.constants import REDIS_URL
from api.services.tenant.access_control import assert_same_tenant
from api.services.tenant.types import TenantContext

_SESSION_ORG_TTL_S = 86400 * 7
_SESSION_ORG_PREFIX = "tenant:session_org:"


async def _redis() -> aioredis.Redis:
    return await aioredis.from_url(REDIS_URL, decode_responses=True)


async def register_session_organization(
    session_id: str,
    organization_id: int,
    *,
    ttl_s: int = _SESSION_ORG_TTL_S,
) -> None:
    if not session_id or organization_id <= 0:
        return
    redis = await _redis()
    await redis.setex(f"{_SESSION_ORG_PREFIX}{session_id}", ttl_s, str(organization_id))


async def lookup_session_organization_id(session_id: str) -> int | None:
    if not session_id:
        return None

    redis = await _redis()
    raw = await redis.get(f"{_SESSION_ORG_PREFIX}{session_id}")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass

    try:
        from api.services.human_escalation.escalation_queues import (
            EscalationQueueService,
        )

        handoff = await EscalationQueueService().get_handoff(session_id)
        if handoff is not None:
            await register_session_organization(session_id, handoff.organization_id)
            return handoff.organization_id
    except Exception:
        pass

    try:
        from api.services.call_reliability.event_store import get_durable_event_store

        events = await get_durable_event_store().list_session_events(
            session_id, limit=1
        )
        if events:
            org_id = events[0].organization_id
            await register_session_organization(session_id, org_id)
            return org_id
    except Exception:
        pass

    try:
        from api.services.voice_cost_optimization.token_tracker import get_token_tracker

        record = await get_token_tracker().get_session_record(session_id)
        if record is not None and record.organization_id > 0:
            await register_session_organization(session_id, record.organization_id)
            return record.organization_id
    except Exception:
        pass

    try:
        from api.services.vertical_workflows.store import get_vertical_workflow_store

        instance = get_vertical_workflow_store().get(session_id)
        if instance is not None:
            await register_session_organization(session_id, instance.organization_id)
            return instance.organization_id
    except Exception:
        pass

    try:
        from api.services.call_routing.queue_service import CallRoutingQueueService

        entry = await CallRoutingQueueService().get_entry(session_id)
        if entry is not None:
            await register_session_organization(session_id, entry.organization_id)
            return entry.organization_id
    except Exception:
        pass

    return None


async def assert_session_belongs_to_tenant(
    ctx: TenantContext,
    session_id: str,
) -> int:
    org_id = await lookup_session_organization_id(session_id)
    if org_id is None:
        raise HTTPException(status_code=404, detail="Session not found")
    assert_same_tenant(ctx, org_id)
    return org_id


async def assert_workflow_run_belongs_to_tenant(
    ctx: TenantContext,
    workflow_run_id: int,
) -> None:
    from api.db import db_client

    run = await db_client.get_workflow_run_by_id(workflow_run_id)
    if run is None or run.workflow is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    assert_same_tenant(ctx, run.workflow.organization_id)


async def assert_campaign_belongs_to_tenant(
    ctx: TenantContext,
    campaign_id: int,
) -> None:
    from api.db import db_client

    campaign = await db_client.get_campaign(campaign_id, ctx.organization_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")


async def assert_customer_belongs_to_tenant(
    ctx: TenantContext,
    customer_id: int,
) -> None:
    from api.db import db_client

    customer = await db_client.get_customer(customer_id, organization_id=ctx.organization_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
