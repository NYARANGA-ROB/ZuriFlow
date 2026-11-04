"""Database operations for Kenyan continuous learning."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select

from api.db.base_client import BaseDBClient
from api.db.models import (
    KenyanLearningFeedbackModel,
    KenyanLearningLabelTaskModel,
    KenyanLearningSampleModel,
    KenyanLearningTrainingRunModel,
)


class KenyanContinuousLearningClient(BaseDBClient):
    async def create_kenyan_learning_sample(
        self,
        *,
        organization_id: int,
        target: str,
        source: str,
        payload: dict[str, Any],
        run_reference_hash: str | None = None,
        locale: str = "mixed",
        metadata: dict[str, Any] | None = None,
    ) -> KenyanLearningSampleModel:
        async with self.async_session() as session:
            row = KenyanLearningSampleModel(
                organization_id=organization_id,
                target=target,
                source=source,
                run_reference_hash=run_reference_hash,
                locale=locale,
                payload=payload,
                metadata_json=metadata or {},
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_kenyan_learning_samples(
        self,
        organization_id: int,
        *,
        target: str | None = None,
        from_ts: datetime | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[KenyanLearningSampleModel], int]:
        async with self.async_session() as session:
            filters = [KenyanLearningSampleModel.organization_id == organization_id]
            if target:
                filters.append(KenyanLearningSampleModel.target == target)
            if from_ts is not None:
                filters.append(KenyanLearningSampleModel.created_at >= from_ts)
            base = select(KenyanLearningSampleModel).where(*filters)
            total = int(
                (await session.execute(select(func.count()).select_from(base.subquery())))
                .scalar_one()
                or 0
            )
            result = await session.execute(
                base.order_by(desc(KenyanLearningSampleModel.created_at))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all()), total

    async def create_label_task(
        self,
        *,
        organization_id: int,
        sample_id: int,
        target: str,
    ) -> KenyanLearningLabelTaskModel:
        async with self.async_session() as session:
            row = KenyanLearningLabelTaskModel(
                organization_id=organization_id,
                sample_id=sample_id,
                target=target,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_label_tasks(
        self,
        organization_id: int,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[KenyanLearningLabelTaskModel], int]:
        async with self.async_session() as session:
            filters = [KenyanLearningLabelTaskModel.organization_id == organization_id]
            if status:
                filters.append(KenyanLearningLabelTaskModel.status == status)
            base = select(KenyanLearningLabelTaskModel).where(*filters)
            total = int(
                (await session.execute(select(func.count()).select_from(base.subquery())))
                .scalar_one()
                or 0
            )
            result = await session.execute(
                base.order_by(desc(KenyanLearningLabelTaskModel.created_at))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all()), total

    async def update_label_task(
        self,
        task_id: int,
        *,
        organization_id: int,
        status: str | None = None,
        label_payload: dict[str, Any] | None = None,
        notes: str | None = None,
        assigned_user_id: int | None = None,
    ) -> KenyanLearningLabelTaskModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(KenyanLearningLabelTaskModel)
                .where(
                    KenyanLearningLabelTaskModel.id == task_id,
                    KenyanLearningLabelTaskModel.organization_id == organization_id,
                )
                .with_for_update()
            )
            row = result.scalars().first()
            if not row:
                return None
            if status is not None:
                row.status = status
            if label_payload is not None:
                row.label_payload = label_payload
            if notes is not None:
                row.notes = notes
            if assigned_user_id is not None:
                row.assigned_user_id = assigned_user_id
            await session.commit()
            await session.refresh(row)
            return row

    async def ingest_feedback(
        self,
        *,
        organization_id: int,
        feedback_type: str,
        payload: dict[str, Any],
        sample_id: int | None = None,
        user_id: int | None = None,
    ) -> KenyanLearningFeedbackModel:
        async with self.async_session() as session:
            row = KenyanLearningFeedbackModel(
                organization_id=organization_id,
                feedback_type=feedback_type,
                payload=payload,
                sample_id=sample_id,
                user_id=user_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_feedback(
        self,
        organization_id: int,
        *,
        feedback_type: str | None = None,
        limit: int = 100,
    ) -> list[KenyanLearningFeedbackModel]:
        async with self.async_session() as session:
            filters = [KenyanLearningFeedbackModel.organization_id == organization_id]
            if feedback_type:
                filters.append(KenyanLearningFeedbackModel.feedback_type == feedback_type)
            result = await session.execute(
                select(KenyanLearningFeedbackModel)
                .where(*filters)
                .order_by(desc(KenyanLearningFeedbackModel.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    async def create_training_run(
        self,
        *,
        organization_id: int,
        targets: list[str],
    ) -> KenyanLearningTrainingRunModel:
        async with self.async_session() as session:
            row = KenyanLearningTrainingRunModel(
                organization_id=organization_id,
                targets=targets,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def update_training_run(
        self,
        run_id: int,
        *,
        organization_id: int,
        **fields: Any,
    ) -> KenyanLearningTrainingRunModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(KenyanLearningTrainingRunModel)
                .where(
                    KenyanLearningTrainingRunModel.id == run_id,
                    KenyanLearningTrainingRunModel.organization_id == organization_id,
                )
                .with_for_update()
            )
            row = result.scalars().first()
            if not row:
                return None
            for key, value in fields.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_training_run(
        self, run_id: int, *, organization_id: int
    ) -> KenyanLearningTrainingRunModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(KenyanLearningTrainingRunModel).where(
                    KenyanLearningTrainingRunModel.id == run_id,
                    KenyanLearningTrainingRunModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def list_training_runs(
        self, organization_id: int, *, limit: int = 20
    ) -> list[KenyanLearningTrainingRunModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(KenyanLearningTrainingRunModel)
                .where(KenyanLearningTrainingRunModel.organization_id == organization_id)
                .order_by(desc(KenyanLearningTrainingRunModel.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_sample(self, sample_id: int, *, organization_id: int):
        async with self.async_session() as session:
            result = await session.execute(
                select(KenyanLearningSampleModel).where(
                    KenyanLearningSampleModel.id == sample_id,
                    KenyanLearningSampleModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()
