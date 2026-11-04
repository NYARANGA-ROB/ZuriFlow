"""Database access for conversation intelligence and insights."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert

from api.db.base_client import BaseDBClient
from api.db.models import (
    BusinessInsightModel,
    ConversationIntelligenceModel,
    MpesaTransactionModel,
    WorkflowModel,
    WorkflowRunModel,
)


class BusinessIntelligenceClient(BaseDBClient):
    async def upsert_conversation_intelligence(
        self,
        *,
        organization_id: int,
        workflow_run_id: int | None,
        payload: dict[str, Any],
    ) -> ConversationIntelligenceModel:
        async with self.async_session() as session:
            values = {
                "organization_id": organization_id,
                "workflow_run_id": workflow_run_id,
                "category": payload["category"],
                "intent": payload.get("intent"),
                "sentiment": payload.get("sentiment") or "neutral",
                "outcome": payload.get("outcome"),
                "unresolved_issue": payload.get("unresolved_issue"),
                "requested_product": payload.get("requested_product"),
                "next_action": payload.get("next_action"),
                "language": payload.get("language"),
                "county": payload.get("county"),
                "contained": bool(payload.get("contained", True)),
                "transferred": bool(payload.get("transferred", False)),
                "first_contact_resolved": bool(
                    payload.get("first_contact_resolved")
                    or payload.get("first_contact_resolved")
                    or False
                ),
                "redacted_excerpt": payload.get("redacted_excerpt")
                or payload.get("redacted_excerpt"),
                "metadata_json": payload.get("metadata") or {},
            }
            if workflow_run_id is not None:
                stmt = (
                    insert(ConversationIntelligenceModel)
                    .values(**values)
                    .on_conflict_do_update(
                        constraint="uq_conv_intel_org_run",
                        set_={
                            key: values[key]
                            for key in values
                            if key not in {"organization_id", "workflow_run_id"}
                        },
                    )
                    .returning(ConversationIntelligenceModel)
                )
                result = await session.execute(stmt)
                row = result.scalars().first()
                await session.commit()
                return row

            row = ConversationIntelligenceModel(**values)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_conversation_intelligence(
        self,
        organization_id: int,
        *,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 200,
    ) -> list[ConversationIntelligenceModel]:
        async with self.async_session() as session:
            stmt = select(ConversationIntelligenceModel).where(
                ConversationIntelligenceModel.organization_id == organization_id
            )
            if from_dt is not None:
                stmt = stmt.where(ConversationIntelligenceModel.created_at >= from_dt)
            if to_dt is not None:
                stmt = stmt.where(ConversationIntelligenceModel.created_at <= to_dt)
            stmt = stmt.order_by(ConversationIntelligenceModel.created_at.desc()).limit(
                limit
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert_business_insight(
        self,
        *,
        organization_id: int,
        kind: str,
        headline: str,
        detail: str | None,
        severity: str,
        window_start: datetime | None,
        window_end: datetime | None,
        metadata: dict[str, Any] | None = None,
    ) -> BusinessInsightModel:
        async with self.async_session() as session:
            row = BusinessInsightModel(
                organization_id=organization_id,
                kind=kind,
                headline=headline,
                detail=detail,
                severity=severity,
                window_start=window_start,
                window_end=window_end,
                metadata_json=metadata or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_business_insights(
        self,
        organization_id: int,
        *,
        limit: int = 20,
    ) -> list[BusinessInsightModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessInsightModel)
                .where(BusinessInsightModel.organization_id == organization_id)
                .order_by(BusinessInsightModel.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def call_volume_stats(
        self,
        organization_id: int,
        *,
        from_dt: datetime,
        to_dt: datetime,
    ) -> dict[str, Any]:
        async with self.async_session() as session:
            stmt = (
                select(
                    func.count(WorkflowRunModel.id),
                    func.sum(
                        case((WorkflowRunModel.is_completed.is_(True), 1), else_=0)
                    ),
                )
                .join(WorkflowModel, WorkflowModel.id == WorkflowRunModel.workflow_id)
                .where(WorkflowModel.organization_id == organization_id)
                .where(WorkflowRunModel.created_at >= from_dt)
                .where(WorkflowRunModel.created_at <= to_dt)
            )
            row = (await session.execute(stmt)).one()
            total = int(row[0] or 0)
            completed = int(row[1] or 0)
            return {
                "total_calls": total,
                "completed_calls": completed,
                "avg_duration_s": 0.0,
            }

    async def payment_volume_stats(
        self,
        organization_id: int,
        *,
        from_dt: datetime,
        to_dt: datetime,
    ) -> dict[str, Any]:
        async with self.async_session() as session:
            stmt = (
                select(
                    MpesaTransactionModel.status,
                    func.count(MpesaTransactionModel.id),
                    func.coalesce(func.sum(MpesaTransactionModel.amount), 0.0),
                )
                .where(MpesaTransactionModel.organization_id == organization_id)
                .where(MpesaTransactionModel.created_at >= from_dt)
                .where(MpesaTransactionModel.created_at <= to_dt)
                .group_by(MpesaTransactionModel.status)
            )
            rows = (await session.execute(stmt)).all()
        by_status = {str(r[0]): {"count": int(r[1]), "amount": float(r[2])} for r in rows}
        total = sum(v["count"] for v in by_status.values())
        success = by_status.get("success") or by_status.get("completed") or {"count": 0, "amount": 0.0}
        failed = by_status.get("failed") or {"count": 0, "amount": 0.0}
        pending = by_status.get("pending") or {"count": 0, "amount": 0.0}
        return {
            "attempts": total,
            "success_count": success["count"],
            "failed_count": failed["count"],
            "abandoned_count": pending["count"],
            "kes_processed": round(success["amount"], 2),
            "by_status": by_status,
        }

    async def list_runs_for_classification(
        self,
        organization_id: int,
        *,
        from_dt: datetime,
        to_dt: datetime,
        limit: int = 150,
    ) -> list[WorkflowRunModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(WorkflowRunModel)
                .join(WorkflowModel, WorkflowModel.id == WorkflowRunModel.workflow_id)
                .where(WorkflowModel.organization_id == organization_id)
                .where(WorkflowRunModel.created_at >= from_dt)
                .where(WorkflowRunModel.created_at <= to_dt)
                .order_by(WorkflowRunModel.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
