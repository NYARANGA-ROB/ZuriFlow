"""TTS personality middleware — transforms text before synthesis."""

from __future__ import annotations

import re

from pipecat.utils.text.base_text_filter import BaseTextFilter

from api.services.kenyan_voice_personality.schema import ResolvedVoicePersonality
from api.services.kenyan_voice_personality.tone import get_tone_configuration_system

_EMPHASIS_RE = re.compile(r"\*\*(.+?)\*\*")
_FILLER_INSERTION_THRESHOLD = 0.7


class KenyanVoicePersonalityMiddleware:
    """Apply personality-specific text shaping for TTS input."""

    def __init__(self, resolved: ResolvedVoicePersonality) -> None:
        self._resolved = resolved
        self._tone_system = get_tone_configuration_system()

    def transform_for_tts(self, text: str, *, was_interrupted: bool = False) -> str:
        if not text.strip():
            return text

        result = text.strip()
        result = _EMPHASIS_RE.sub(r"\1", result)
        result = self._apply_register(result)
        result = self._apply_emotional_markers(result, was_interrupted=was_interrupted)
        return result

    def _apply_register(self, text: str) -> str:
        register = self._resolved.tone.register.value
        if register == "formal":
            text = text.replace("yeah", "yes").replace("ok", "okay")
        elif register == "casual":
            text = text.replace("Certainly,", "Sure,").replace("Certainly.", "Sure.")
        return text

    def _apply_emotional_markers(self, text: str, *, was_interrupted: bool) -> str:
        tone = self._resolved.tone
        if was_interrupted and self._resolved.profile.playback.acknowledge_interrupt:
            prefix = "Sawa — " if tone.empathy > 0.5 else "Okay — "
            if not text.lower().startswith(("sawa", "okay", "pole")):
                text = prefix + text

        warmth_prefix = self._tone_system.warmth_prefix(tone)
        if warmth_prefix and tone.warmth > _FILLER_INSERTION_THRESHOLD:
            if not text.startswith(warmth_prefix):
                text = f"{warmth_prefix} {text}"

        if tone.urgency > 0.65:
            text = re.sub(r"\bplease wait\b", "one moment", text, flags=re.IGNORECASE)

        return text


class KenyanVoicePersonalityTextFilter(BaseTextFilter):
    """Pipecat TTS text filter wired to a resolved Kenyan voice personality."""

    def __init__(self, resolved: ResolvedVoicePersonality) -> None:
        self._middleware = KenyanVoicePersonalityMiddleware(resolved)
        self._was_interrupted = False

    def set_interrupted(self, interrupted: bool) -> None:
        self._was_interrupted = interrupted

    async def filter(self, text: str) -> str:
        return self._middleware.transform_for_tts(
            text, was_interrupted=self._was_interrupted
        )

    async def reset_interruption(self) -> None:
        self._was_interrupted = False
