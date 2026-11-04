"""Calibrated confidence scoring for accent predictions."""

from __future__ import annotations

import numpy as np

from api.services.kenyan_accent.config import KenyanAccentConfig
from api.services.kenyan_accent.types import (
    AccentClass,
    AccentPrediction,
    AccentScores,
    ConfidenceFactors,
)


class ConfidenceScorer:
    """Combine model probability with telephony quality factors."""

    def __init__(self, config: KenyanAccentConfig) -> None:
        self._config = config

    def score(
        self,
        scores: AccentScores,
        *,
        snr_db: float,
        speech_ratio: float,
        segment_duration_s: float,
        model_entropy: float,
        pyannote_used: bool,
        session_id: str | None = None,
        history: list[AccentClass] | None = None,
        stable_required: int | None = None,
    ) -> AccentPrediction:
        cfg = self._config
        label = scores.top_label
        probability = scores.top_probability

        snr_penalty = 0.0
        if snr_db < cfg.min_snr_db:
            snr_penalty = (cfg.min_snr_db - snr_db) * cfg.snr_penalty_scale

        duration_bonus = min(
            segment_duration_s / cfg.duration_bonus_cap_s,
            1.0,
        ) * 0.08

        speech_penalty = 0.0
        if speech_ratio < 0.35:
            speech_penalty = (0.35 - speech_ratio) * 0.2

        entropy_penalty = model_entropy * 0.15

        confidence = float(
            np.clip(
                probability - snr_penalty - speech_penalty - entropy_penalty + duration_bonus,
                0.0,
                1.0,
            )
        )

        stable_n = stable_required if stable_required is not None else cfg.stable_predictions_required
        is_stable = False
        if history is not None and len(history) >= stable_n:
            recent = history[-stable_n:]
            is_stable = len(set(recent)) == 1 and recent[-1] == label

        factors = ConfidenceFactors(
            snr_db=snr_db,
            speech_ratio=speech_ratio,
            segment_duration_s=segment_duration_s,
            model_entropy=model_entropy,
            pyannote_used=pyannote_used,
        )

        return AccentPrediction(
            label=label,
            probability=probability,
            confidence=confidence,
            scores=scores,
            factors=factors,
            is_stable=is_stable,
            session_id=session_id,
        )

    def meets_threshold(self, prediction: AccentPrediction) -> bool:
        return prediction.confidence >= self._config.min_confidence
