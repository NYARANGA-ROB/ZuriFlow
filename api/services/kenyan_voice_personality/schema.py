"""Voice profile and tone configuration schema for Kenyan AI personalities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class KenyanVoiceStyle(str, Enum):
    NAIROBI_PROFESSIONAL = "nairobi_professional"
    FRIENDLY_RECEPTIONIST = "friendly_receptionist"
    SACCO_COLLECTIONS_OFFICER = "sacco_collections_officer"
    LOGISTICS_DISPATCHER = "logistics_dispatcher"


class EmotionalTone(str, Enum):
    NEUTRAL = "neutral"
    WARM = "warm"
    EMPATHETIC = "empathetic"
    FIRM = "firm"
    URGENT = "urgent"
    REASSURING = "reassuring"


class ConversationalRegister(str, Enum):
    FORMAL = "formal"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    MIXED_KE = "mixed_ke"


@dataclass(frozen=True)
class MultilingualVoiceSettings:
    """Per-locale voice behavior."""

    primary_locale: str = "mixed"
    supported_locales: tuple[str, ...] = ("en", "sw", "mixed")
    code_switch_ratio: float = 0.35
    prefer_swahili_greetings: bool = False
    localized_fillers_en: tuple[str, ...] = ("sure", "okay", "right")
    localized_fillers_sw: tuple[str, ...] = ("sawa", "ndiyo", "pole")

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_locale": self.primary_locale,
            "supported_locales": list(self.supported_locales),
            "code_switch_ratio": self.code_switch_ratio,
            "prefer_swahili_greetings": self.prefer_swahili_greetings,
            "localized_fillers_en": list(self.localized_fillers_en),
            "localized_fillers_sw": list(self.localized_fillers_sw),
        }


@dataclass(frozen=True)
class ToneConfiguration:
    """Conversational tone knobs applied on top of a voice profile."""

    emotional_tone: EmotionalTone = EmotionalTone.NEUTRAL
    register: ConversationalRegister = ConversationalRegister.PROFESSIONAL
    warmth: float = 0.5
    assertiveness: float = 0.5
    empathy: float = 0.5
    urgency: float = 0.3
    humor: float = 0.1
    max_words_per_sentence: int | None = None
    max_sentences_per_turn: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "emotional_tone": self.emotional_tone.value,
            "register": self.register.value,
            "warmth": self.warmth,
            "assertiveness": self.assertiveness,
            "empathy": self.empathy,
            "urgency": self.urgency,
            "humor": self.humor,
            "max_words_per_sentence": self.max_words_per_sentence,
            "max_sentences_per_turn": self.max_sentences_per_turn,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ToneConfiguration:
        if not raw:
            return cls()
        tone = raw.get("emotional_tone", EmotionalTone.NEUTRAL.value)
        reg = raw.get("register", ConversationalRegister.PROFESSIONAL.value)
        return cls(
            emotional_tone=EmotionalTone(tone),
            register=ConversationalRegister(reg),
            warmth=float(raw.get("warmth", 0.5)),
            assertiveness=float(raw.get("assertiveness", 0.5)),
            empathy=float(raw.get("empathy", 0.5)),
            urgency=float(raw.get("urgency", 0.3)),
            humor=float(raw.get("humor", 0.1)),
            max_words_per_sentence=raw.get("max_words_per_sentence"),
            max_sentences_per_turn=raw.get("max_sentences_per_turn"),
        )


@dataclass(frozen=True)
class PlaybackAdaptationSettings:
    """Interruption-aware TTS playback parameters."""

    barge_in_enabled: bool = True
    post_interrupt_pause_ms: int = 280
    resume_soft_start_ms: int = 120
    truncate_on_interrupt: bool = True
    acknowledge_interrupt: bool = True
    max_tts_chunk_chars: int = 80
    base_pause_ms: int = 120
    comma_pause_ms: int = 200
    sentence_pause_ms: int = 350
    speed_multiplier: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "barge_in_enabled": self.barge_in_enabled,
            "post_interrupt_pause_ms": self.post_interrupt_pause_ms,
            "resume_soft_start_ms": self.resume_soft_start_ms,
            "truncate_on_interrupt": self.truncate_on_interrupt,
            "acknowledge_interrupt": self.acknowledge_interrupt,
            "max_tts_chunk_chars": self.max_tts_chunk_chars,
            "base_pause_ms": self.base_pause_ms,
            "comma_pause_ms": self.comma_pause_ms,
            "sentence_pause_ms": self.sentence_pause_ms,
            "speed_multiplier": self.speed_multiplier,
        }


@dataclass(frozen=True)
class TTSVoiceMapping:
    """Provider voice mapping for a personality profile."""

    provider: str = "dograh"
    voice_id: str = "default"
    speed: float = 1.0
    language: str = "multi"
    pitch_shift: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "language": self.language,
            "pitch_shift": self.pitch_shift,
        }


@dataclass(frozen=True)
class KenyanVoiceProfile:
    """Complete localized Kenyan voice personality definition."""

    profile_id: str
    style: KenyanVoiceStyle
    name: str
    description: str
    icon: str
    domain: str
    default_tone: ToneConfiguration
    multilingual: MultilingualVoiceSettings
    playback: PlaybackAdaptationSettings
    tts_mapping: TTSVoiceMapping
    system_prompt_overlay: str = ""
    tags: tuple[str, ...] = ()
    search_keywords: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "style": self.style.value,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "domain": self.domain,
            "default_tone": self.default_tone.to_dict(),
            "multilingual": self.multilingual.to_dict(),
            "playback": self.playback.to_dict(),
            "tts_mapping": self.tts_mapping.to_dict(),
            "system_prompt_overlay": self.system_prompt_overlay,
            "tags": list(self.tags),
            "search_keywords": list(self.search_keywords),
        }


@dataclass
class ResolvedVoicePersonality:
    """Fully resolved profile + tone for runtime use."""

    profile: KenyanVoiceProfile
    tone: ToneConfiguration
    effective_speed: float
    conversation_config_overrides: dict[str, Any] = field(default_factory=dict)
