"""Tenant-scoped Digital Twin persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.db.base_client import BaseDBClient
from api.db.models import (
    BusinessAgentTraceModel,
    BusinessAlertModel,
    BusinessAnnouncementModel,
    BusinessApprovalModel,
    BusinessConflictModel,
    BusinessContactModel,
    BusinessDataChangeModel,
    BusinessDataSnapshotModel,
    BusinessDataSourceModel,
    BusinessEventModel,
    BusinessFaqModel,
    BusinessFieldVersionModel,
    BusinessHolidayModel,
    BusinessHoursModel,
    BusinessInterviewSessionModel,
    BusinessLocationModel,
    BusinessOfferingModel,
    BusinessOverrideModel,
    BusinessPolicyModel,
    BusinessProfileModel,
    BusinessPromotionModel,
    BusinessSourceAuthorityModel,
    BusinessSyncErrorModel,
    BusinessSyncJobModel,
    BusinessSyncRunModel,
    BusinessUnansweredQuestionModel,
)


class BusinessTwinClient(BaseDBClient):
    async def get_business_profile(self, organization_id: int) -> BusinessProfileModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessProfileModel).where(
                    BusinessProfileModel.organization_id == organization_id
                )
            )
            return result.scalars().first()

    async def upsert_business_profile(
        self, organization_id: int, **fields: Any
    ) -> BusinessProfileModel:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessProfileModel).where(
                    BusinessProfileModel.organization_id == organization_id
                )
            )
            row = result.scalars().first()
            if row is None:
                row = BusinessProfileModel(organization_id=organization_id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    if hasattr(row, key) and value is not None:
                        setattr(row, key, value)
                row.updated_at = datetime.now(UTC)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                result = await session.execute(
                    select(BusinessProfileModel).where(
                        BusinessProfileModel.organization_id == organization_id
                    )
                )
                row = result.scalars().first()
                if row is None:
                    raise
            await session.refresh(row)
            return row

    async def list_locations(self, organization_id: int) -> list[BusinessLocationModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessLocationModel).where(
                    BusinessLocationModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def add_location(self, organization_id: int, **fields: Any) -> BusinessLocationModel:
        async with self.async_session() as session:
            row = BusinessLocationModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_hours(self, organization_id: int) -> list[BusinessHoursModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessHoursModel).where(
                    BusinessHoursModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def replace_hours(
        self, organization_id: int, rows: list[dict[str, Any]]
    ) -> list[BusinessHoursModel]:
        async with self.async_session() as session:
            existing = await session.execute(
                select(BusinessHoursModel).where(
                    BusinessHoursModel.organization_id == organization_id
                )
            )
            for item in existing.scalars().all():
                await session.delete(item)
            created: list[BusinessHoursModel] = []
            for payload in rows:
                row = BusinessHoursModel(organization_id=organization_id, **payload)
                session.add(row)
                created.append(row)
            await session.commit()
            for row in created:
                await session.refresh(row)
            return created

    async def list_offerings(
        self, organization_id: int, *, kind: str | None = None
    ) -> list[BusinessOfferingModel]:
        async with self.async_session() as session:
            stmt = select(BusinessOfferingModel).where(
                BusinessOfferingModel.organization_id == organization_id
            )
            if kind:
                stmt = stmt.where(BusinessOfferingModel.kind == kind)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def add_offering(self, organization_id: int, **fields: Any) -> BusinessOfferingModel:
        async with self.async_session() as session:
            row = BusinessOfferingModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_policies(self, organization_id: int) -> list[BusinessPolicyModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessPolicyModel).where(
                    BusinessPolicyModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def add_policy(self, organization_id: int, **fields: Any) -> BusinessPolicyModel:
        async with self.async_session() as session:
            row = BusinessPolicyModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_faqs(self, organization_id: int) -> list[BusinessFaqModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessFaqModel).where(
                    BusinessFaqModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def add_faq(self, organization_id: int, **fields: Any) -> BusinessFaqModel:
        async with self.async_session() as session:
            row = BusinessFaqModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_contacts(self, organization_id: int) -> list[BusinessContactModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessContactModel).where(
                    BusinessContactModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def add_contact(self, organization_id: int, **fields: Any) -> BusinessContactModel:
        async with self.async_session() as session:
            row = BusinessContactModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_announcements(
        self, organization_id: int
    ) -> list[BusinessAnnouncementModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessAnnouncementModel).where(
                    BusinessAnnouncementModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def list_holidays(self, organization_id: int) -> list[BusinessHolidayModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessHolidayModel).where(
                    BusinessHolidayModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def add_source(self, organization_id: int, **fields: Any) -> BusinessDataSourceModel:
        async with self.async_session() as session:
            row = BusinessDataSourceModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_source(
        self, organization_id: int, source_id: int
    ) -> BusinessDataSourceModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessDataSourceModel).where(
                    BusinessDataSourceModel.id == source_id,
                    BusinessDataSourceModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def list_sources(self, organization_id: int) -> list[BusinessDataSourceModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessDataSourceModel).where(
                    BusinessDataSourceModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())

    async def latest_snapshot(
        self, organization_id: int, source_id: int
    ) -> BusinessDataSnapshotModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessDataSnapshotModel)
                .where(
                    BusinessDataSnapshotModel.organization_id == organization_id,
                    BusinessDataSnapshotModel.source_id == source_id,
                )
                .order_by(BusinessDataSnapshotModel.id.desc())
                .limit(1)
            )
            return result.scalars().first()

    async def add_snapshot(
        self, organization_id: int, source_id: int, payload: dict[str, Any], record_count: int
    ) -> BusinessDataSnapshotModel:
        async with self.async_session() as session:
            row = BusinessDataSnapshotModel(
                organization_id=organization_id,
                source_id=source_id,
                payload_json=payload,
                record_count=record_count,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def add_change(self, organization_id: int, **fields: Any) -> BusinessDataChangeModel:
        async with self.async_session() as session:
            row = BusinessDataChangeModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_change(
        self, organization_id: int, change_id: int
    ) -> BusinessDataChangeModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessDataChangeModel).where(
                    BusinessDataChangeModel.id == change_id,
                    BusinessDataChangeModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def list_changes(
        self, organization_id: int, *, status: str | None = None
    ) -> list[BusinessDataChangeModel]:
        async with self.async_session() as session:
            stmt = select(BusinessDataChangeModel).where(
                BusinessDataChangeModel.organization_id == organization_id
            )
            if status:
                stmt = stmt.where(BusinessDataChangeModel.status == status)
            stmt = stmt.order_by(BusinessDataChangeModel.id.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_change(
        self, organization_id: int, change_id: int, **fields: Any
    ) -> BusinessDataChangeModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessDataChangeModel).where(
                    BusinessDataChangeModel.id == change_id,
                    BusinessDataChangeModel.organization_id == organization_id,
                )
            )
            row = result.scalars().first()
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            await session.commit()
            await session.refresh(row)
            return row

    async def add_conflict(self, organization_id: int, **fields: Any) -> BusinessConflictModel:
        async with self.async_session() as session:
            row = BusinessConflictModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_conflicts(
        self, organization_id: int, *, open_only: bool = True
    ) -> list[BusinessConflictModel]:
        async with self.async_session() as session:
            stmt = select(BusinessConflictModel).where(
                BusinessConflictModel.organization_id == organization_id
            )
            if open_only:
                stmt = stmt.where(BusinessConflictModel.resolution_status == "open")
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def resolve_conflict(
        self,
        organization_id: int,
        conflict_id: int,
        *,
        resolved_source: str,
        user_id: int | None,
    ) -> BusinessConflictModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessConflictModel).where(
                    BusinessConflictModel.id == conflict_id,
                    BusinessConflictModel.organization_id == organization_id,
                )
            )
            row = result.scalars().first()
            if row is None:
                return None
            row.resolution_status = "resolved"
            row.resolved_source = resolved_source
            row.resolved_by_user_id = user_id
            await session.commit()
            await session.refresh(row)
            return row

    async def add_approval(self, organization_id: int, **fields: Any) -> BusinessApprovalModel:
        async with self.async_session() as session:
            row = BusinessApprovalModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def add_event(self, organization_id: int, **fields: Any) -> BusinessEventModel:
        async with self.async_session() as session:
            row = BusinessEventModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def add_alert(self, organization_id: int, **fields: Any) -> BusinessAlertModel:
        async with self.async_session() as session:
            row = BusinessAlertModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_alerts(self, organization_id: int) -> list[BusinessAlertModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessAlertModel)
                .where(
                    BusinessAlertModel.organization_id == organization_id,
                    BusinessAlertModel.is_open.is_(True),
                )
                .order_by(BusinessAlertModel.id.desc())
            )
            return list(result.scalars().all())

    async def add_sync_job(self, organization_id: int, **fields: Any) -> BusinessSyncJobModel:
        async with self.async_session() as session:
            row = BusinessSyncJobModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def due_sync_jobs(self, now: datetime) -> list[BusinessSyncJobModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessSyncJobModel).where(
                    BusinessSyncJobModel.enabled.is_(True),
                    (BusinessSyncJobModel.next_run_at.is_(None))
                    | (BusinessSyncJobModel.next_run_at <= now),
                )
            )
            return list(result.scalars().all())

    async def add_sync_run(self, organization_id: int, **fields: Any) -> BusinessSyncRunModel:
        async with self.async_session() as session:
            row = BusinessSyncRunModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def finish_sync_run(
        self, organization_id: int, run_id: int, **fields: Any
    ) -> BusinessSyncRunModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessSyncRunModel).where(
                    BusinessSyncRunModel.id == run_id,
                    BusinessSyncRunModel.organization_id == organization_id,
                )
            )
            row = result.scalars().first()
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            await session.commit()
            await session.refresh(row)
            return row

    async def add_sync_error(self, organization_id: int, **fields: Any) -> BusinessSyncErrorModel:
        async with self.async_session() as session:
            row = BusinessSyncErrorModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_sync_runs(
        self, organization_id: int, *, limit: int = 20
    ) -> list[BusinessSyncRunModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessSyncRunModel)
                .where(BusinessSyncRunModel.organization_id == organization_id)
                .order_by(BusinessSyncRunModel.id.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def add_field_version(
        self, organization_id: int, **fields: Any
    ) -> BusinessFieldVersionModel:
        async with self.async_session() as session:
            row = BusinessFieldVersionModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_field_versions(
        self, organization_id: int, entity_type: str, entity_id: int, field_path: str
    ) -> list[BusinessFieldVersionModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessFieldVersionModel)
                .where(
                    BusinessFieldVersionModel.organization_id == organization_id,
                    BusinessFieldVersionModel.entity_type == entity_type,
                    BusinessFieldVersionModel.entity_id == entity_id,
                    BusinessFieldVersionModel.field_path == field_path,
                )
                .order_by(BusinessFieldVersionModel.version.desc())
            )
            return list(result.scalars().all())

    async def get_authority(
        self, organization_id: int, data_type: str
    ) -> BusinessSourceAuthorityModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessSourceAuthorityModel).where(
                    BusinessSourceAuthorityModel.organization_id == organization_id,
                    BusinessSourceAuthorityModel.data_type == data_type,
                )
            )
            return result.scalars().first()

    async def upsert_authority(
        self, organization_id: int, data_type: str, ranked: list[str]
    ) -> BusinessSourceAuthorityModel:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessSourceAuthorityModel).where(
                    BusinessSourceAuthorityModel.organization_id == organization_id,
                    BusinessSourceAuthorityModel.data_type == data_type,
                )
            )
            row = result.scalars().first()
            if row is None:
                row = BusinessSourceAuthorityModel(
                    organization_id=organization_id,
                    data_type=data_type,
                    ranked_sources_json=ranked,
                )
                session.add(row)
            else:
                row.ranked_sources_json = ranked
            await session.commit()
            await session.refresh(row)
            return row

    async def add_interview(
        self, organization_id: int, **fields: Any
    ) -> BusinessInterviewSessionModel:
        async with self.async_session() as session:
            row = BusinessInterviewSessionModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_interview(
        self, organization_id: int, session_id: int
    ) -> BusinessInterviewSessionModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessInterviewSessionModel).where(
                    BusinessInterviewSessionModel.id == session_id,
                    BusinessInterviewSessionModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def update_source(self, organization_id: int, source_id: int, **fields: Any):
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessDataSourceModel).where(
                    BusinessDataSourceModel.id == source_id,
                    BusinessDataSourceModel.organization_id == organization_id,
                )
            )
            row = result.scalars().first()
            if row is None:
                return None
            for key, value in fields.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            await session.commit()
            await session.refresh(row)
            return row

    async def add_trace(self, organization_id: int, **fields: Any) -> BusinessAgentTraceModel:
        async with self.async_session() as session:
            row = BusinessAgentTraceModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_traces(
        self, organization_id: int, *, limit: int = 50
    ) -> list[BusinessAgentTraceModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessAgentTraceModel)
                .where(BusinessAgentTraceModel.organization_id == organization_id)
                .order_by(BusinessAgentTraceModel.id.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def bump_unanswered(
        self,
        organization_id: int,
        question_redacted: str,
        intent: str | None,
        missing_field: str | None,
    ) -> BusinessUnansweredQuestionModel:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessUnansweredQuestionModel).where(
                    BusinessUnansweredQuestionModel.organization_id == organization_id,
                    BusinessUnansweredQuestionModel.question_redacted == question_redacted,
                )
            )
            row = result.scalars().first()
            if row:
                row.hit_count = int(row.hit_count or 1) + 1
                row.updated_at = datetime.now(UTC)
            else:
                row = BusinessUnansweredQuestionModel(
                    organization_id=organization_id,
                    question_redacted=question_redacted,
                    intent=intent,
                    missing_field=missing_field,
                )
                session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_unanswered(
        self, organization_id: int, *, limit: int = 20
    ) -> list[BusinessUnansweredQuestionModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessUnansweredQuestionModel)
                .where(BusinessUnansweredQuestionModel.organization_id == organization_id)
                .order_by(BusinessUnansweredQuestionModel.hit_count.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def add_override(self, organization_id: int, **fields: Any) -> BusinessOverrideModel:
        async with self.async_session() as session:
            row = BusinessOverrideModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def active_overrides(self, organization_id: int) -> list[BusinessOverrideModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessOverrideModel).where(
                    BusinessOverrideModel.organization_id == organization_id
                )
            )
            now = datetime.now(UTC)
            return [
                row
                for row in result.scalars().all()
                if row.expires_at is None or row.expires_at > now
            ]

    async def add_promotion(self, organization_id: int, **fields: Any) -> BusinessPromotionModel:
        async with self.async_session() as session:
            row = BusinessPromotionModel(organization_id=organization_id, **fields)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_promotions(self, organization_id: int) -> list[BusinessPromotionModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BusinessPromotionModel).where(
                    BusinessPromotionModel.organization_id == organization_id
                )
            )
            return list(result.scalars().all())
