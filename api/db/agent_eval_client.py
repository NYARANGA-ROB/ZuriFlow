"""Organization-scoped persistence for agent evaluation runs."""
from __future__ import annotations
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select

from api.db.base_client import BaseDBClient
from api.db.models import (
    AgentEvalProductionSampleModel,
    AgentEvalResultModel,
    AgentEvalRunModel,
    WorkflowDefinitionModel,
    WorkflowModel,
)


class AgentEvalClient(BaseDBClient):
    async def create_eval_run(
        self,
        *,
        organization_id: int,
        workflow_id: int | None,
        workflow_definition_id: int | None,
        baseline_definition_id: int | None,
        trigger: str,
        status: str,
        scenario_filter: str | None,
        score_json: dict[str, Any],
        comparison_json: dict[str, Any],
        metrics_json: dict[str, Any],
    ) -> AgentEvalRunModel:
        async with self.async_session() as session:
            row = AgentEvalRunModel(
                organization_id=organization_id,
                workflow_id=workflow_id,
                workflow_definition_id=workflow_definition_id,
                baseline_definition_id=baseline_definition_id,
                trigger=trigger,
                status=status,
                scenario_filter=scenario_filter,
                score_json=score_json,
                comparison_json=comparison_json,
                metrics_json=metrics_json,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def add_eval_result(
        self,
        *,
        organization_id: int,
        run_id: int,
        scenario_id: str,
        category: str,
        passed: bool,
        expected_json: dict[str, Any],
        actual_json: dict[str, Any],
        evaluation_json: dict[str, Any],
        transcript_json: list[Any],
        tool_calls_json: list[Any],
        workflow_path_json: list[Any],
        latency_ms: float | None,
    ) -> AgentEvalResultModel:
        async with self.async_session() as session:
            row = AgentEvalResultModel(
                organization_id=organization_id,
                run_id=run_id,
                scenario_id=scenario_id,
                category=category,
                passed=passed,
                expected_json=expected_json,
                actual_json=actual_json,
                evaluation_json=evaluation_json,
                transcript_json=transcript_json,
                tool_calls_json=tool_calls_json,
                workflow_path_json=workflow_path_json,
                latency_ms=latency_ms,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_eval_run(
        self, run_id: int, *, organization_id: int
    ) -> AgentEvalRunModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(AgentEvalRunModel).where(
                    AgentEvalRunModel.id == run_id,
                    AgentEvalRunModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def list_eval_runs(
        self,
        organization_id: int,
        *,
        workflow_id: int | None = None,
        limit: int = 50,
    ) -> list[AgentEvalRunModel]:
        async with self.async_session() as session:
            filters = [AgentEvalRunModel.organization_id == organization_id]
            if workflow_id is not None:
                filters.append(AgentEvalRunModel.workflow_id == workflow_id)
            result = await session.execute(
                select(AgentEvalRunModel)
                .where(*filters)
                .order_by(desc(AgentEvalRunModel.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    async def list_eval_results(
        self, run_id: int, *, organization_id: int
    ) -> list[AgentEvalResultModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(AgentEvalResultModel)
                .where(
                    AgentEvalResultModel.run_id == run_id,
                    AgentEvalResultModel.organization_id == organization_id,
                )
                .order_by(AgentEvalResultModel.id)
            )
            return list(result.scalars().all())

    async def get_eval_result(
        self, result_id: int, *, organization_id: int
    ) -> AgentEvalResultModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(AgentEvalResultModel).where(
                    AgentEvalResultModel.id == result_id,
                    AgentEvalResultModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def get_previous_archived_definition(
        self, workflow_id: int, *, organization_id: int, current_definition_id: int | None
    ) -> WorkflowDefinitionModel | None:
        async with self.async_session() as session:
            wf = await session.execute(
                select(WorkflowModel.id).where(
                    WorkflowModel.id == workflow_id,
                    WorkflowModel.organization_id == organization_id,
                )
            )
            if wf.scalar_one_or_none() is None:
                return None
            filters = [
                WorkflowDefinitionModel.workflow_id == workflow_id,
                WorkflowDefinitionModel.status == "archived",
            ]
            if current_definition_id is not None:
                filters.append(WorkflowDefinitionModel.id != current_definition_id)
            result = await session.execute(
                select(WorkflowDefinitionModel)
                .where(*filters)
                .order_by(desc(WorkflowDefinitionModel.published_at))
                .limit(1)
            )
            return result.scalars().first()

    async def insert_production_sample(
        self,
        *,
        organization_id: int,
        workflow_id: int | None,
        run_reference_hash: str | None,
        consent_ok: bool,
        anonymized_turns: list[Any],
        training_eligible: bool = False,
        governance_note: str | None = None,
    ) -> AgentEvalProductionSampleModel:
        async with self.async_session() as session:
            row = AgentEvalProductionSampleModel(
                organization_id=organization_id,
                workflow_id=workflow_id,
                run_reference_hash=run_reference_hash,
                consent_ok=consent_ok,
                anonymized_turns=anonymized_turns,
                training_eligible=False if not consent_ok else training_eligible,
                governance_note=governance_note,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list_production_samples(
        self, organization_id: int, *, limit: int = 50
    ) -> list[AgentEvalProductionSampleModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(AgentEvalProductionSampleModel)
                .where(AgentEvalProductionSampleModel.organization_id == organization_id)
                .order_by(desc(AgentEvalProductionSampleModel.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    async def set_training_eligible(
        self,
        sample_id: int,
        *,
        organization_id: int,
        eligible: bool,
        governance_note: str,
    ) -> AgentEvalProductionSampleModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(AgentEvalProductionSampleModel).where(
                    AgentEvalProductionSampleModel.id == sample_id,
                    AgentEvalProductionSampleModel.organization_id == organization_id,
                )
            )
            row = result.scalars().first()
            if row is None:
                return None
            if eligible and not row.consent_ok:
                raise ValueError("Cannot mark training-eligible without recorded consent")
            row.training_eligible = eligible
            row.governance_note = governance_note
            await session.commit()
            await session.refresh(row)
            return row
