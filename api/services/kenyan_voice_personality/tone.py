"""Tone configuration system — maps emotional tone to runtime parameters."""

from __future__ import annotations

from dataclasses import replace

from api.services.kenyan_voice_personality.schema import (
    EmotionalTone,
    KenyanVoiceProfile,
    ResolvedVoicePersonality,
    ToneConfiguration,
)

_TONE_SPEED_DELTA: dict[EmotionalTone, float] = {
    EmotionalTone.NEUTRAL: 0.0,
    EmotionalTone.WARM: -0.03,
    EmotionalTone.EMPATHETIC: -0.02,
    EmotionalTone.FIRM: 0.02,
    EmotionalTone.URGENT: 0.06,
    EmotionalTone.REASSURING: -0.04,
}

_TONE_WARMTH_PHRASES: dict[EmotionalTone, tuple[str, ...]] = {
    EmotionalTone.WARM: ("Happy to help.",),
    EmotionalTone.EMPATHETIC: ("I understand.", "Pole for the inconvenience."),
    EmotionalTone.REASSURING: ("Don't worry, we'll sort this out.",),
    EmotionalTone.FIRM: (),
    EmotionalTone.URGENT: (),
    EmotionalTone.NEUTRAL: (),
}


class ToneConfigurationSystem:
    """Merge profile defaults with tone overrides and compute effective settings."""

    def merge_tone(
        self,
        profile: KenyanVoiceProfile,
        override: ToneConfiguration | None,
    ) -> ToneConfiguration:
        base = profile.default_tone
        if override is None:
            return base
        return ToneConfiguration(
            emotional_tone=override.emotional_tone
            if override.emotional_tone != EmotionalTone.NEUTRAL
            else base.emotional_tone,
            register=override.register if override.register else base.register,
            warmth=override.warmth if override.warmth != 0.5 else base.warmth,
            assertiveness=(
                override.assertiveness
                if override.assertiveness != 0.5
                else base.assertiveness
            ),
            empathy=override.empathy if override.empathy != 0.5 else base.empathy,
            urgency=override.urgency if override.urgency != 0.3 else base.urgency,
            humor=override.humor if override.humor != 0.1 else base.humor,
            max_words_per_sentence=override.max_words_per_sentence
            or base.max_words_per_sentence,
            max_sentences_per_turn=override.max_sentences_per_turn
            or base.max_sentences_per_turn,
        )

    def resolve(
        self,
        profile: KenyanVoiceProfile,
        tone_override: ToneConfiguration | None = None,
    ) -> ResolvedVoicePersonality:
        tone = self.merge_tone(profile, tone_override)
        speed = profile.playback.speed_multiplier
        speed += _TONE_SPEED_DELTA.get(tone.emotional_tone, 0.0)
        speed += (tone.urgency - 0.5) * 0.08
        speed = max(0.75, min(1.25, speed))

        conversation_overrides: dict = {
            "domain": profile.domain,
            "language_mode": profile.multilingual.primary_locale
            if profile.multilingual.primary_locale != "mixed"
            else "mixed",
            "max_words_per_sentence": tone.max_words_per_sentence or 18,
            "max_sentences_per_turn": tone.max_sentences_per_turn or 3,
            "post_interrupt_pause_ms": profile.playback.post_interrupt_pause_ms,
            "max_tts_chunk_chars": profile.playback.max_tts_chunk_chars,
            "base_pause_ms": profile.playback.base_pause_ms,
            "comma_pause_ms": profile.playback.comma_pause_ms,
            "sentence_pause_ms": profile.playback.sentence_pause_ms,
            "acknowledge_interrupts": profile.playback.acknowledge_interrupt,
            "prefer_short_replies": tone.urgency > 0.5,
        }

        return ResolvedVoicePersonality(
            profile=profile,
            tone=tone,
            effective_speed=round(speed, 3),
            conversation_config_overrides=conversation_overrides,
        )

    def warmth_prefix(self, tone: ToneConfiguration) -> str | None:
        phrases = _TONE_WARMTH_PHRASES.get(tone.emotional_tone, ())
        return phrases[0] if phrases and tone.warmth > 0.6 else None


_tone_system: ToneConfigurationSystem | None = None


def get_tone_configuration_system() -> ToneConfigurationSystem:
    global _tone_system
    if _tone_system is None:
        _tone_system = ToneConfigurationSystem()
    return _tone_system
