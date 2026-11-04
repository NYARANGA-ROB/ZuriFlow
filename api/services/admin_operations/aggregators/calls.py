"""Realtime call monitoring aggregation."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.services.realtime_audio.connection_manager import get_connection_manager
from api.services.realtime_voice_pipeline.session_registry import (
    get_voice_pipeline_registry,
)


class CallsAggregator:
    async def live_snapshot(self, organization_id: int) -> dict[str, Any]:
        manager = get_connection_manager()
        registry = get_voice_pipeline_registry()
        sessions = manager.snapshot_sessions()
        org_sessions = [
            s
            for s in sessions
            if int(s.get("metadata", {}).get("organization_id", 0) or 0)
            == organization_id
        ]
        active_audio = sum(1 for s in org_sessions if s.get("active"))
        grace_audio = sum(1 for s in org_sessions if s.get("in_grace"))
        active_pipelines = sum(
            1
            for s in org_sessions
            if registry.has_active(s["session_id"])
        )

        incomplete_runs = await db_client.get_incomplete_workflow_runs(
            organization_id, limit=25
        )
        return {
            "organization_id": organization_id,
            "active_audio_sessions": active_audio,
            "grace_period_sessions": grace_audio,
            "active_voice_pipelines": active_pipelines,
            "total_registered_sessions": manager.session_count(),
            "incomplete_workflow_runs": len(incomplete_runs),
            "recent_incomplete_runs": incomplete_runs,
            "audio_sessions": org_sessions[:50],
        }

    async def recent_runs(
        self,
        organization_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        from datetime import datetime, timedelta, timezone

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        runs, total = await db_client.search_workflow_runs(
            organization_id,
            from_ts=start,
            to_ts=end,
            limit=limit,
            offset=offset,
        )
        return {
            "organization_id": organization_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "runs": runs,
        }
