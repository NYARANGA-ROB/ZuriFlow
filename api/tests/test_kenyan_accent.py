"""Tests for Kenyan accent detection (no GPU / pyannote required)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from api.services.kenyan_accent.confidence import ConfidenceScorer
from api.services.kenyan_accent.config import KenyanAccentConfig
from api.services.kenyan_accent.preprocessing import PhoneAudioPreprocessor, pcm16_to_float32
from api.services.kenyan_accent.segmentation import SpeechSegmenter
from api.services.kenyan_accent.types import AccentClass, AccentScores


def _tone_pcm(duration_s: float = 1.0, freq: float = 280.0, sample_rate: int = 16000) -> bytes:
    t = np.arange(int(duration_s * sample_rate)) / sample_rate
    wave = (0.4 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    return wave.tobytes()


def test_pcm16_roundtrip():
    pcm = _tone_pcm(0.1)
    wave = pcm16_to_float32(pcm)
    assert wave.shape[0] == int(0.1 * 16000)
    assert float(np.max(np.abs(wave))) <= 1.0


def test_preprocessor_outputs_16k():
    cfg = KenyanAccentConfig(enabled=True, pyannote_token=None)
    pre = PhoneAudioPreprocessor(cfg)
    wave = pcm16_to_float32(_tone_pcm(0.5, sample_rate=8000))
    out, sr, snr = pre.process(wave, 8000)
    assert sr == 16000
    assert out.size > 0
    assert snr > -10.0


def test_energy_segmenter_finds_speech():
    cfg = KenyanAccentConfig(enabled=True, pyannote_token=None)
    seg = SpeechSegmenter(cfg)
    wave = pcm16_to_float32(_tone_pcm(1.0))
    segments = seg.segment(wave, 16000)
    assert len(segments) >= 1


def test_confidence_scorer_penalizes_low_snr():
    cfg = KenyanAccentConfig()
    scorer = ConfidenceScorer(cfg)
    scores = AccentScores(generic_english=0.3, kenyan_english=0.7)
    good = scorer.score(
        scores,
        snr_db=20.0,
        speech_ratio=0.8,
        segment_duration_s=1.5,
        model_entropy=0.3,
        pyannote_used=False,
    )
    bad = scorer.score(
        scores,
        snr_db=2.0,
        speech_ratio=0.8,
        segment_duration_s=1.5,
        model_entropy=0.3,
        pyannote_used=False,
    )
    assert good.confidence > bad.confidence
    assert good.label == AccentClass.KENYAN_ENGLISH


def test_confidence_stability_requires_consensus():
    cfg = KenyanAccentConfig(stable_predictions_required=2)
    scorer = ConfidenceScorer(cfg)
    scores = AccentScores(generic_english=0.2, kenyan_english=0.8)
    unstable = scorer.score(
        scores,
        snr_db=15.0,
        speech_ratio=0.7,
        segment_duration_s=1.0,
        model_entropy=0.2,
        pyannote_used=False,
        history=[AccentClass.GENERIC_ENGLISH],
    )
    stable = scorer.score(
        scores,
        snr_db=15.0,
        speech_ratio=0.7,
        segment_duration_s=1.0,
        model_entropy=0.2,
        pyannote_used=False,
        history=[AccentClass.KENYAN_ENGLISH, AccentClass.KENYAN_ENGLISH],
    )
    assert not unstable.is_stable
    assert stable.is_stable


@pytest.mark.asyncio
async def test_hook_dispatches_stable_prediction():
    from api.services.kenyan_accent.hooks import KenyanAccentHook
    from api.services.kenyan_accent.types import AccentPrediction, ConfidenceFactors

    mock_service = MagicMock()
    mock_service.start_session = AsyncMock(return_value="sess1")
    mock_service.push_chunk = AsyncMock(
        return_value=AccentPrediction(
            label=AccentClass.KENYAN_ENGLISH,
            probability=0.85,
            confidence=0.8,
            scores=AccentScores(0.15, 0.85),
            factors=ConfidenceFactors(12.0, 0.7, 1.2, 0.2, False),
            is_stable=True,
            session_id="sess1",
        )
    )
    callback = AsyncMock()
    hook = KenyanAccentHook(service=mock_service, on_stable_kenyan=callback, min_confidence=0.5)
    await hook.on_call_started(call_id="call-1")
    await hook.on_inbound_audio(_tone_pcm(0.5))
    callback.assert_awaited_once()
