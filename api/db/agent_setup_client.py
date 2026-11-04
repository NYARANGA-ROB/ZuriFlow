"""Database access for agent setup wizard sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.future import select

from api.db.base_client import BaseDBClient
from api.db.models import AgentSetupSessionModel


class AgentSetupClient(BaseDBClient):
    async def create_agent_setup_session(
        self,
        *,
        session_uuid: str,
        organization_id: int,
        user_id: int,
        state: str,
        config: dict[str, Any],
    ) -> AgentSetupSessionModel:
        async with self.async_session() as session:
            row = AgentSetupSessionModel(
                session_uuid=session_uuid,
                organization_id=organization_id,
                user_id=user_id,
                state=state,
                config=config,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_agent_setup_session_by_uuid(
        self,
        session_uuid: str,
    ) -> AgentSetupSessionModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(AgentSetupSessionModel).where(
                    AgentSetupSessionModel.session_uuid == session_uuid
                )
            )
            return result.scalar_one_or_none()

    async def get_active_agent_setup_session(
        self,
        *,
        organization_id: int,
        user_id: int,
    ) -> AgentSetupSessionModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(AgentSetupSessionModel)
                .where(
                    AgentSetupSessionModel.organization_id == organization_id,
                    AgentSetupSessionModel.user_id == user_id,
                    AgentSetupSessionModel.state.notin_(("completed", "failed")),
                )
                .order_by(AgentSetupSessionModel.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def update_agent_setup_session(
        self,
        session_id: int,
        *,
        state: str | None = None,
        config: dict[str, Any] | None = None,
        workflow_id: int | None = None,
        phone_number_id: int | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> AgentSetupSessionModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(AgentSetupSessionModel).where(
                    AgentSetupSessionModel.id == session_id
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            if state is not None:
                row.state = state
            if config is not None:
                row.config = config
            if workflow_id is not None:
                row.workflow_id = workflow_id
            if phone_number_id is not None:
                row.phone_number_id = phone_number_id
            if error_message is not None:
                row.error_message = error_message
            if completed_at is not None:
                row.completed_at = completed_at
            await session.commit()
            await session.refresh(row)
            return row
