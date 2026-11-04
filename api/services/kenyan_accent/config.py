"""Configuration for Kenyan accent detection."""

from __future__ import annotations

from dataclasses import dataclass

from api.constants import (
    KENYAN_ACCENT_ENABLED,
    KENYAN_ACCENT_MODEL_PATH,
    PYANNOTE_AUTH_TOKEN,
)


@dataclass(frozen=True)
class KenyanAccentConfig:
    """Tunables for phone-call accent classification."""

    enabled: bool = KENYAN_ACCENT_ENABLED
    model_path: str | None = KENYAN_ACCENT_MODEL_PATH
    pyannote_token: str | None = PYANNOTE_AUTH_TOKEN

    # Telephony audio
    target_sample_rate: int = 16000
    telephony_low_hz: float = 300.0
    telephony_high_hz: float = 3400.0

    # Feature extraction
    n_mfcc: int = 20
    n_mels: int = 64
    n_fft: int = 512
    hop_length: int = 160  # 10 ms @ 16 kHz
    win_length: int = 400  # 25 ms @ 16 kHz

    # Realtime sliding window
    window_s: float = 2.0
    hop_s: float = 0.5
    min_speech_s: float = 0.4
    stable_predictions_required: int = 2

    # Confidence calibration
    min_snr_db: float = 6.0
    min_confidence: float = 0.55
    snr_penalty_scale: float = 0.02
    duration_bonus_cap_s: float = 3.0

    # Pyannote segmentation
    pyannote_segmentation_model: str = "pyannote/segmentation-3.0"
    pyannote_min_speech_s: float = 0.15
    pyannote_min_silence_s: float = 0.1

    # Inference
    device: str = "cpu"
    inference_timeout_s: float = 0.25


DEFAULT_KENYAN_ACCENT_CONFIG = KenyanAccentConfig()
