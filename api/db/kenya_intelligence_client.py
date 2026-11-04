"""CRUD for Kenyan phrase catalog rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from api.db.base_client import BaseDBClient
from api.db.models import KenyanPhraseEntryModel


class KenyaIntelligenceClient(BaseDBClient):
    async def list_kenyan_phrases(
        self,
        *,
        organization_id: int,
        include_global: bool = True,
        active_only: bool = False,
    ) -> list[KenyanPhraseEntryModel]:
        async with self.async_session() as session:
            cond = KenyanPhraseEntryModel.organization_id == organization_id
            if include_global:
                cond = or_(cond, KenyanPhraseEntryModel.organization_id.is_(None))
            stmt = select(KenyanPhraseEntryModel).where(cond)
            if active_only:
                stmt = stmt.where(KenyanPhraseEntryModel.is_active.is_(True))
            stmt = stmt.order_by(KenyanPhraseEntryModel.phrase)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_kenyan_phrase(
        self,
        *,
        organization_id: int | None,
        phrase: str,
        meaning: str,
        language: str = "sheng",
        intent: str | None = None,
        confidence: float = 0.85,
        context: str | None = None,
        region: str = "national",
        version: str = "1",
        is_active: bool = True,
    ) -> KenyanPhraseEntryModel:
        async with self.async_session() as session:
            row = KenyanPhraseEntryModel(
                organization_id=organization_id,
                phrase=phrase.strip().lower(),
                meaning=meaning.strip(),
                language=language,
                intent=intent,
                confidence=confidence,
                context=context,
                region=region,
                version=version,
                is_active=is_active,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def update_kenyan_phrase(
        self,
        phrase_id: int,
        *,
        organization_id: int,
        allow_global: bool,
        fields: dict[str, Any],
    ) -> KenyanPhraseEntryModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(KenyanPhraseEntryModel).where(KenyanPhraseEntryModel.id == phrase_id)
            )
            row = result.scalars().first()
            if row is None:
                return None
            if row.organization_id is None and not allow_global:
                return None
            if row.organization_id is not None and row.organization_id != organization_id:
                return None
            for key, value in fields.items():
                if value is not None and hasattr(row, key):
                    setattr(row, key, value)
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return row
