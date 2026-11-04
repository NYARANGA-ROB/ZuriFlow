"""Public omnichannel engagement service."""

from __future__ import annotations

from typing import Any

from api.constants import OMNICHANNEL_ENABLED
from api.services.omnichannel.consent import get_consent_service
from api.services.omnichannel.conversations import get_conversation_service
from api.services.omnichannel.followups import get_followup_engine
from api.services.omnichannel.identity import get_customer_identity_service
from api.services.omnichannel.orchestrator import get_channel_orchestrator
from api.services.omnichannel.types import Channel, FollowupTrigger, MessagePurpose


class OmnichannelService:
    @property
    def enabled(self) -> bool:
        return OMNICHANNEL_ENABLED

    async def resolve_identity(self, **kwargs: Any):
        return await get_customer_identity_service().resolve(**kwargs)

    async def orchestrate(self, **kwargs: Any) -> dict[str, Any]:
        return await get_channel_orchestrator().execute(**kwargs)

    async def ingest_inbound(self, **kwargs: Any) -> dict[str, Any]:
        return await get_channel_orchestrator().ingest_inbound(**kwargs)

    async def handle_followup(self, **kwargs: Any) -> list[dict[str, Any]]:
        return await get_followup_engine().handle(**kwargs)

    async def conversation_timeline(self, **kwargs: Any) -> dict[str, Any]:
        return await get_conversation_service().timeline(**kwargs)

    async def update_preferences(self, **kwargs: Any):
        return await get_consent_service().update(**kwargs)

    async def get_preferences(self, **kwargs: Any):
        return await get_consent_service().get_or_create(**kwargs)

    async def dashboard(self, *, organization_id: int, days: int = 30) -> dict[str, Any]:
        from api.db import db_client

        metrics = await db_client.engagement_metrics(
            organization_id=organization_id, days=days
        )
        return {"enabled": self.enabled, **metrics}


_service: OmnichannelService | None = None


def get_omnichannel_service() -> OmnichannelService:
    global _service
    if _service is None:
        _service = OmnichannelService()
    return _service


__all__ = [
    "Channel",
    "FollowupTrigger",
    "MessagePurpose",
    "OmnichannelService",
    "get_omnichannel_service",
]
