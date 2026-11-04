"""Map Kenyan voice personality profiles to ElevenLabs voice IDs."""

from __future__ import annotations

import os
import re
from typing import Optional, Tuple

from api.constants import KENYAN_VOICE_PERSONALITY_ENABLED
from api.services.kenyan_voice_personality.resolver import get_voice_personality_resolver

# Abstract profile keys from KenyanVoiceProfile.tts_mapping.voice_id
KENYAN_ELEVENLABS_VOICE_MAP: dict[str, str] = {
    "professional": os.getenv(
        "KENYAN_ELEVENLABS_VOICE_PROFESSIONAL",
        "pNInz6obpgDQGcFmaJgB",
    ),
    "warm": os.getenv(
        "KENYAN_ELEVENLABS_VOICE_WARM",
        "EXAVITQu4vr4xnSDxMaL",
    ),
    "firm": os.getenv(
        "KENYAN_ELEVENLABS_VOICE_FIRM",
        "onwK4e9ZLuTAKqWW03F9",
    ),
    "default": os.getenv(
        "KENYAN_ELEVENLABS_VOICE_DEFAULT",
        "pNInz6obpgDQGcFmaJgB",
    ),
}

_ELEVENLABS_VOICE_ID_RE = re.compile(r"^[A-Za-z0-9]{15,30}$")


def _looks_like_elevenlabs_voice_id(voice: str) -> bool:
    if " - " in voice:
        voice = voice.split(" - ", 1)[1]
    return bool(_ELEVENLABS_VOICE_ID_RE.match(voice.strip()))


def map_profile_voice_key(voice_key: str) -> str:
    """Resolve an abstract profile voice key to a concrete ElevenLabs voice ID."""
    return KENYAN_ELEVENLABS_VOICE_MAP.get(voice_key, voice_key)


async def resolve_elevenlabs_voice_for_org(
    organization_id: int | None,
    configured_voice: str,
    configured_speed: float | None,
) -> Tuple[str, Optional[float]]:
    """Apply org Kenyan voice personality to ElevenLabs TTS settings.

    Returns ``(voice_id, speed)`` where speed may be overridden by the profile.
    When personality is disabled or the configured voice already looks like a
    concrete ElevenLabs ID, the caller's values are returned unchanged.
    """
    try:
        voice_id = configured_voice.split(" - ")[1]
    except IndexError:
        voice_id = configured_voice

    speed = configured_speed

    if not KENYAN_VOICE_PERSONALITY_ENABLED or organization_id is None:
        return voice_id, speed

    if _looks_like_elevenlabs_voice_id(voice_id):
        return voice_id, speed

    resolver = get_voice_personality_resolver()
    org_cfg = await resolver.load_org_selection(organization_id)
    profile_id = org_cfg.get("profile_id")
    if not profile_id:
        return map_profile_voice_key(voice_id), speed

    personality = await resolver.resolve(str(profile_id), organization_id=organization_id)
    profile_voice = personality.profile.tts_mapping.voice_id
    mapped_voice = map_profile_voice_key(profile_voice)
    profile_speed = personality.profile.tts_mapping.speed
    if profile_speed and profile_speed != 1.0:
        speed = profile_speed
    return mapped_voice, speed
