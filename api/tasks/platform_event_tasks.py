"""ARQ tasks for platform event routing and retries."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client
from api.services.platform_events.dlq import get_platform_event_dlq
from api.services.platform_events.router import get_platform_event_router
from api.services.platform_events.schema import PlatformEvent


async def route_platform_event(_ctx: dict[str, Any], event_id: str) -> dict[str, Any]:
    row = await db_client.get_platform_event(event_id)
    if row is None:
        return {"routed": False, "reason": "not_found"}
    event = PlatformEvent.from_db_row(row)
    result = await get_platform_event_router().dispatch(event)
    return {"routed": True, "event_id": event_id, **result}


async def process_platform_event_retries(
    _ctx: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Drain due handler retries for one or more organizations."""
    dlq = get_platform_event_dlq()
    router = get_platform_event_router()
    org_ids: list[int] = []
    if payload and payload.get("organization_ids"):
        org_ids = [int(x) for x in payload["organization_ids"]]
    elif payload and payload.get("organization_id"):
        org_ids = [int(payload["organization_id"])]
    else:
        org_ids = await dlq.scan_organization_ids_with_retries()

    processed = 0
    failed = 0
    for org_id in org_ids:
        due = await dlq.claim_due_retries(org_id, limit=50)
        for item in due:
            row = await db_client.get_platform_event(str(item.get("event_id")))
            if row is None:
                failed += 1
                continue
            event = PlatformEvent.from_db_row(row)
            result = await router.dispatch(
                event,
                handler_name=str(item.get("handler_name") or ""),
                attempt=int(item.get("attempt") or 1),
            )
            processed += 1
            failed += int(result.get("failed") or 0)

    logger.info(
        "platform event retries orgs={} processed={} failed={}",
        len(org_ids),
        processed,
        failed,
    )
    return {"organizations": len(org_ids), "processed": processed, "failed": failed}
