"""Tests for Kenyan voice personality → ElevenLabs TTS mapping."""

from unittest.mock import AsyncMock, patch

import pytest

from api.services.kenyan_voice_personality.profiles import NAIROBI_PROFESSIONAL
from api.services.kenyan_voice_personality.schema import ResolvedVoicePersonality
from api.services.kenyan_voice_personality.tts_mapping import (
    map_profile_voice_key,
    resolve_elevenlabs_voice_for_org,
)


def test_map_profile_voice_key():
    assert map_profile_voice_key("professional") != "professional"
    assert map_profile_voice_key("unknown_key") == "unknown_key"


@pytest.mark.asyncio
async def test_resolve_skips_concrete_elevenlabs_id():
    voice_id, speed = await resolve_elevenlabs_voice_for_org(
        organization_id=1,
        configured_voice="Rachel - pNInz6obpgDQGcFmaJgB",
        configured_speed=1.0,
    )
    assert voice_id == "pNInz6obpgDQGcFmaJgB"
    assert speed == 1.0


@pytest.mark.asyncio
async def test_resolve_applies_org_profile():
    personality = ResolvedVoicePersonality(
        profile=NAIROBI_PROFESSIONAL,
        tone=NAIROBI_PROFESSIONAL.default_tone,
        effective_speed=NAIROBI_PROFESSIONAL.tts_mapping.speed,
    )
    mock_resolver = AsyncMock()
    mock_resolver.load_org_selection = AsyncMock(
        return_value={"profile_id": "nairobi_professional"}
    )
    mock_resolver.resolve = AsyncMock(return_value=personality)

    with patch(
        "api.services.kenyan_voice_personality.tts_mapping.get_voice_personality_resolver",
        return_value=mock_resolver,
    ):
        voice_id, speed = await resolve_elevenlabs_voice_for_org(
            organization_id=42,
            configured_voice="placeholder",
            configured_speed=1.0,
        )

    assert voice_id == map_profile_voice_key("professional")
    assert speed == NAIROBI_PROFESSIONAL.tts_mapping.speed
