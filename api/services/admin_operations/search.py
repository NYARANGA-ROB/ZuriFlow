"""Cross-entity search for admin operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.db import db_client


class AdminSearchService:
    async def search_runs(
        self,
        organization_id: int,
        *,
        q: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        from_ts: float | None = None,
        to_ts: float | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        from_dt = (
            datetime.fromtimestamp(from_ts, tz=timezone.utc) if from_ts else None
        )
        to_dt = datetime.fromtimestamp(to_ts, tz=timezone.utc) if to_ts else None
        runs, total = await db_client.search_workflow_runs(
            organization_id,
            q=q,
            filters=filters,
            from_ts=from_dt,
            to_ts=to_dt,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
        return {
            "entity": "workflow_run",
            "organization_id": organization_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": runs,
        }

    async def search_campaigns(
        self,
        organization_id: int,
        *,
        q: str | None = None,
        state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        rows, total = await db_client.search_campaigns(
            organization_id,
            q=q,
            state=state,
            limit=limit,
            offset=offset,
        )
        return {
            "entity": "campaign",
            "organization_id": organization_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [
                {
                    "id": c.id,
                    "name": c.name,
                    "state": c.state,
                    "workflow_id": c.workflow_id,
                    "processed_rows": c.processed_rows,
                    "failed_rows": c.failed_rows,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in rows
            ],
        }

    async def search_payments(
        self,
        organization_id: int,
        *,
        q: str | None = None,
        status: str | None = None,
        from_ts: float | None = None,
        to_ts: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        from api.services.admin_operations.aggregators.payments import PaymentsAggregator

        return await PaymentsAggregator().search(
            organization_id,
            q=q,
            status=status,
            from_ts=from_ts,
            to_ts=to_ts,
            limit=limit,
            offset=offset,
        )
