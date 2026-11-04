"""Resolve voice profiles with tone and org-level selection."""

from __future__ import annotations

from typing import Any

from api.enums import OrganizationConfigurationKey
from api.services.kenyan_voice_personality.registry import get_kenyan_voice_profile_registry
from api.services.kenyan_voice_personality.schema import (
    ResolvedVoicePersonality,
    ToneConfiguration,
)
from api.services.kenyan_voice_personality.tone import get_tone_configuration_system

ORG_CONFIG_KEY = OrganizationConfigurationKey.VOICE_PERSONALITY_CONFIGURATION.value


class VoicePersonalityResolver:
    def __init__(self) -> None:
        self._registry = get_kenyan_voice_profile_registry()
        self._tone = get_tone_configuration_system()

    async def load_org_selection(self, organization_id: int) -> dict[str, Any]:
        try:
            from api.db import db_client

            row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
            return dict(row.value) if row and row.value else {}
        except Exception:
            return {}

    async def save_org_selection(
        self,
        organization_id: int,
        *,
        profile_id: str,
        tone: ToneConfiguration | None = None,
    ) -> dict[str, Any]:
        from api.db import db_client

        self._registry.require(profile_id)
        value: dict[str, Any] = {"profile_id": profile_id}
        if tone is not None:
            value["tone"] = tone.to_dict()
        await db_client.upsert_configuration(organization_id, ORG_CONFIG_KEY, value)
        return value

    async def resolve(
        self,
        profile_id: str,
        *,
        organization_id: int | None = None,
        tone_override: ToneConfiguration | None = None,
    ) -> ResolvedVoicePersonality:
        if organization_id is not None:
            org_cfg = await self.load_org_selection(organization_id)
            if not profile_id and org_cfg.get("profile_id"):
                profile_id = str(org_cfg["profile_id"])
            if tone_override is None and org_cfg.get("tone"):
                tone_override = ToneConfiguration.from_dict(org_cfg["tone"])

        profile = self._registry.require(profile_id)
        return self._tone.resolve(profile, tone_override)


_resolver: VoicePersonalityResolver | None = None


def get_voice_personality_resolver() -> VoicePersonalityResolver:
    global _resolver
    if _resolver is None:
        _resolver = VoicePersonalityResolver()
    return _resolver
