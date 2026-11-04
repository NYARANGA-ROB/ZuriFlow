"""Types for Kenyan accent detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AccentClass(str, Enum):
    GENERIC_ENGLISH = "generic_english"
    KENYAN_ENGLISH = "kenyan_english"


@dataclass(frozen=True)
class SpeechSegment:
    start_sample: int
    end_sample: int

    @property
    def duration_s(self) -> float:
        return 0.0  # set by caller with sample_rate


@dataclass(frozen=True)
class AccentScores:
    generic_english: float
    kenyan_english: float

    @property
    def top_label(self) -> AccentClass:
        if self.kenyan_english >= self.generic_english:
            return AccentClass.KENYAN_ENGLISH
        return AccentClass.GENERIC_ENGLISH

    @property
    def top_probability(self) -> float:
        return max(self.generic_english, self.kenyan_english)

    @property
    def margin(self) -> float:
        return abs(self.kenyan_english - self.generic_english)


@dataclass(frozen=True)
class ConfidenceFactors:
    snr_db: float
    speech_ratio: float
    segment_duration_s: float
    model_entropy: float
    pyannote_used: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "snr_db": round(self.snr_db, 2),
            "speech_ratio": round(self.speech_ratio, 3),
            "segment_duration_s": round(self.segment_duration_s, 3),
            "model_entropy": round(self.model_entropy, 4),
            "pyannote_used": self.pyannote_used,
        }


@dataclass(frozen=True)
class AccentPrediction:
    """Single accent classification result with calibrated confidence."""

    label: AccentClass
    probability: float
    confidence: float
    scores: AccentScores
    factors: ConfidenceFactors
    is_stable: bool = False
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label.value,
            "probability": round(self.probability, 4),
            "confidence": round(self.confidence, 4),
            "scores": {
                "generic_english": round(self.scores.generic_english, 4),
                "kenyan_english": round(self.scores.kenyan_english, 4),
            },
            "factors": self.factors.to_dict(),
            "is_stable": self.is_stable,
            "session_id": self.session_id,
        }


@dataclass
class StreamingSessionState:
    session_id: str
    sample_rate: int
    pcm_buffer: bytearray = field(default_factory=bytearray)
    prediction_history: list[AccentClass] = field(default_factory=list)
    last_prediction: AccentPrediction | None = None
    total_audio_s: float = 0.0
