"""Database queries for the admin operations dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, and_, case, cast, desc, func, or_, select

from api.db.base_client import BaseDBClient
from api.db.filters import apply_workflow_run_filters, get_workflow_run_order_clause
from api.db.models import (
    CampaignModel,
    MpesaTransactionModel,
    UserModel,
    WorkflowModel,
    WorkflowRunModel,
)


class AdminOperationsClient(BaseDBClient):
    """Aggregations and search for admin dashboard APIs."""

    async def get_mpesa_payment_summary(
        self,
        organization_id: int,
        *,
        from_ts: datetime,
        to_ts: datetime,
    ) -> dict[str, Any]:
        async with self.async_session() as session:
            result = await session.execute(
                select(
                    MpesaTransactionModel.status,
                    func.count(MpesaTransactionModel.id).label("count"),
                    func.coalesce(func.sum(MpesaTransactionModel.amount), 0.0).label(
                        "total_amount"
                    ),
                )
                .where(
                    MpesaTransactionModel.organization_id == organization_id,
                    MpesaTransactionModel.created_at >= from_ts,
                    MpesaTransactionModel.created_at <= to_ts,
                )
                .group_by(MpesaTransactionModel.status)
            )
            by_status: dict[str, dict[str, Any]] = {}
            total_count = 0
            total_amount = 0.0
            for row in result.all():
                status = str(row.status)
                count = int(row.count or 0)
                amount = float(row.total_amount or 0.0)
                by_status[status] = {"count": count, "total_amount": round(amount, 2)}
                total_count += count
                if status in {"completed", "success"}:
                    total_amount += amount
            return {
                "organization_id": organization_id,
                "from_ts": from_ts.isoformat(),
                "to_ts": to_ts.isoformat(),
                "transaction_count": total_count,
                "collected_amount": round(total_amount, 2),
                "currency": "KES",
                "by_status": by_status,
            }

    async def search_mpesa_transactions(
        self,
        organization_id: int,
        *,
        q: str | None = None,
        status: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MpesaTransactionModel], int]:
        async with self.async_session() as session:
            filters = [MpesaTransactionModel.organization_id == organization_id]
            if status:
                filters.append(MpesaTransactionModel.status == status)
            if from_ts is not None:
                filters.append(MpesaTransactionModel.created_at >= from_ts)
            if to_ts is not None:
                filters.append(MpesaTransactionModel.created_at <= to_ts)
            if q:
                pattern = f"%{q.strip()}%"
                filters.append(
                    or_(
                        MpesaTransactionModel.phone_e164.ilike(pattern),
                        MpesaTransactionModel.account_reference.ilike(pattern),
                        MpesaTransactionModel.mpesa_receipt_number.ilike(pattern),
                        MpesaTransactionModel.checkout_request_id.ilike(pattern),
                    )
                )

            base = select(MpesaTransactionModel).where(and_(*filters))
            count_result = await session.execute(
                select(func.count()).select_from(base.subquery())
            )
            total = int(count_result.scalar_one() or 0)

            result = await session.execute(
                base.order_by(desc(MpesaTransactionModel.created_at))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all()), total

    async def get_incomplete_workflow_runs(
        self,
        organization_id: int,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(
                select(WorkflowRunModel, WorkflowModel.name)
                .join(WorkflowModel, WorkflowModel.id == WorkflowRunModel.workflow_id)
                .join(UserModel, UserModel.id == WorkflowModel.user_id)
                .where(
                    UserModel.selected_organization_id == organization_id,
                    WorkflowRunModel.is_completed.is_(False),
                )
                .order_by(WorkflowRunModel.created_at.desc())
                .limit(limit)
            )
            rows: list[dict[str, Any]] = []
            for run, workflow_name in result.all():
                ic = run.initial_context or {}
                rows.append(
                    {
                        "id": run.id,
                        "workflow_id": run.workflow_id,
                        "workflow_name": workflow_name,
                        "campaign_id": run.campaign_id,
                        "call_type": run.call_type,
                        "mode": run.mode,
                        "created_at": run.created_at.isoformat(),
                        "caller_number": ic.get("caller_number"),
                        "called_number": ic.get("called_number")
                        or ic.get("phone_number"),
                    }
                )
            return rows

    async def get_workflow_performance(
        self,
        organization_id: int,
        *,
        from_ts: datetime,
        to_ts: datetime,
        limit: int = 25,
    ) -> dict[str, Any]:
        async with self.async_session() as session:
            duration_expr = WorkflowRunModel.usage_info[
                "call_duration_seconds"
            ].as_float()
            result = await session.execute(
                select(
                    WorkflowRunModel.workflow_id,
                    WorkflowModel.name.label("workflow_name"),
                    func.count(WorkflowRunModel.id).label("run_count"),
                    func.sum(
                        case((WorkflowRunModel.is_completed.is_(True), 1), else_=0)
                    ).label("completed_count"),
                    func.coalesce(func.avg(duration_expr), 0.0).label("avg_duration_s"),
                    func.coalesce(func.sum(duration_expr), 0.0).label(
                        "total_duration_s"
                    ),
                )
                .join(WorkflowModel, WorkflowModel.id == WorkflowRunModel.workflow_id)
                .join(UserModel, UserModel.id == WorkflowModel.user_id)
                .where(
                    UserModel.selected_organization_id == organization_id,
                    WorkflowRunModel.created_at >= from_ts,
                    WorkflowRunModel.created_at <= to_ts,
                )
                .group_by(WorkflowRunModel.workflow_id, WorkflowModel.name)
                .order_by(desc("run_count"))
                .limit(limit)
            )
            workflows: list[dict[str, Any]] = []
            total_runs = 0
            total_completed = 0
            for row in result.all():
                run_count = int(row.run_count or 0)
                completed = int(row.completed_count or 0)
                total_runs += run_count
                total_completed += completed
                workflows.append(
                    {
                        "workflow_id": row.workflow_id,
                        "workflow_name": row.workflow_name,
                        "run_count": run_count,
                        "completed_count": completed,
                        "completion_rate": (
                            round(completed / run_count, 4) if run_count else None
                        ),
                        "avg_duration_s": round(float(row.avg_duration_s or 0.0), 2),
                        "total_duration_s": round(
                            float(row.total_duration_s or 0.0), 2
                        ),
                    }
                )
            return {
                "organization_id": organization_id,
                "from_ts": from_ts.isoformat(),
                "to_ts": to_ts.isoformat(),
                "total_runs": total_runs,
                "completed_runs": total_completed,
                "completion_rate": (
                    round(total_completed / total_runs, 4) if total_runs else None
                ),
                "workflows": workflows,
            }

    async def search_workflow_runs(
        self,
        organization_id: int,
        *,
        q: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        async with self.async_session() as session:
            query = (
                select(WorkflowRunModel, WorkflowModel.name)
                .join(WorkflowModel, WorkflowModel.id == WorkflowRunModel.workflow_id)
                .join(UserModel, UserModel.id == WorkflowModel.user_id)
                .where(UserModel.selected_organization_id == organization_id)
            )
            if from_ts is not None:
                query = query.where(WorkflowRunModel.created_at >= from_ts)
            if to_ts is not None:
                query = query.where(WorkflowRunModel.created_at <= to_ts)
            if q:
                pattern = f"%{q.strip()}%"
                query = query.where(
                    or_(
                        cast(WorkflowRunModel.id, String).ilike(pattern),
                        WorkflowRunModel.initial_context["caller_number"]
                        .astext.ilike(pattern),
                        WorkflowRunModel.initial_context["called_number"]
                        .astext.ilike(pattern),
                        WorkflowRunModel.initial_context["phone_number"]
                        .astext.ilike(pattern),
                        WorkflowModel.name.ilike(pattern),
                    )
                )
            query = apply_workflow_run_filters(query, filters)
            count_query = select(func.count()).select_from(query.subquery())
            total = int((await session.execute(count_query)).scalar_one() or 0)

            query = query.order_by(get_workflow_run_order_clause(sort_by, sort_order))
            result = await session.execute(query.limit(limit).offset(offset))
            rows: list[dict[str, Any]] = []
            for run, workflow_name in result.all():
                usage = run.usage_info or {}
                ic = run.initial_context or {}
                gc = run.gathered_context or {}
                rows.append(
                    {
                        "id": run.id,
                        "workflow_id": run.workflow_id,
                        "workflow_name": workflow_name,
                        "campaign_id": run.campaign_id,
                        "is_completed": run.is_completed,
                        "call_type": run.call_type,
                        "mode": run.mode,
                        "created_at": run.created_at.isoformat(),
                        "call_duration_seconds": usage.get("call_duration_seconds"),
                        "disposition": gc.get("mapped_call_disposition"),
                        "caller_number": ic.get("caller_number"),
                        "called_number": ic.get("called_number")
                        or ic.get("phone_number"),
                    }
                )
            return rows, total

    async def search_campaigns(
        self,
        organization_id: int,
        *,
        q: str | None = None,
        state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CampaignModel], int]:
        async with self.async_session() as session:
            filters = [CampaignModel.organization_id == organization_id]
            if state:
                filters.append(CampaignModel.state == state)
            if q:
                pattern = f"%{q.strip()}%"
                filters.append(CampaignModel.name.ilike(pattern))

            base = select(CampaignModel).where(and_(*filters))
            total = int(
                (await session.execute(select(func.count()).select_from(base.subquery())))
                .scalar_one()
                or 0
            )
            result = await session.execute(
                base.order_by(desc(CampaignModel.created_at)).limit(limit).offset(offset)
            )
            return list(result.scalars().all()), total
