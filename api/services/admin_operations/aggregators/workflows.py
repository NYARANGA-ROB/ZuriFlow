"""Workflow performance aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.db import db_client


class WorkflowsAggregator:
    async def performance(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        days: int = 7,
        limit: int = 25,
    ) -> dict[str, Any]:
        import time

        now = time.time()
        end = to_ts if to_ts is not None else now
        start = from_ts if from_ts is not None else end - days * 86400
        return await db_client.get_workflow_performance(
            organization_id,
            from_ts=datetime.fromtimestamp(start, tz=timezone.utc),
            to_ts=datetime.fromtimestamp(end, tz=timezone.utc),
            limit=limit,
        )
