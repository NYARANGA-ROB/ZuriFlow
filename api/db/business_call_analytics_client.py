"""Database queries for business call analytics fallbacks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Float, cast, func, select

from api.db.base_client import BaseDBClient
from api.db.models import UserModel, WorkflowModel, WorkflowRunModel


class BusinessCallAnalyticsClient(BaseDBClient):
    """Workflow-run aggregates used when event streams are incomplete."""

    async def get_business_call_duration_stats(
        self,
        organization_id: int,
        *,
        from_ts: datetime,
        to_ts: datetime,
    ) -> dict[str, Any]:
        async with self.async_session() as session:
            result = await session.execute(
                select(
                    func.count(WorkflowRunModel.id).label("call_count"),
                    func.coalesce(
                        func.sum(
                            cast(
                                WorkflowRunModel.usage_info["call_duration_seconds"],
                                Float,
                            )
                        ),
                        0.0,
                    ).label("total_duration_s"),
                )
                .join(WorkflowModel, WorkflowModel.id == WorkflowRunModel.workflow_id)
                .join(UserModel, UserModel.id == WorkflowModel.user_id)
                .where(
                    UserModel.selected_organization_id == organization_id,
                    WorkflowRunModel.created_at >= from_ts,
                    WorkflowRunModel.created_at <= to_ts,
                    WorkflowRunModel.is_completed.is_(True),
                    cast(
                        WorkflowRunModel.usage_info["call_duration_seconds"],
                        Float,
                    )
                    > 0,
                )
            )
            row = result.one()
            call_count = int(row.call_count or 0)
            total_duration = float(row.total_duration_s or 0.0)
            return {
                "call_count": call_count,
                "total_duration_s": total_duration,
                "avg_duration_s": (
                    round(total_duration / call_count, 2) if call_count else None
                ),
            }
