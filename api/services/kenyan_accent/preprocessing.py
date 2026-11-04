"""Telephony audio preprocessing for accent detection."""

from __future__ import annotations

import numpy as np

from api.services.kenyan_accent.config import KenyanAccentConfig


def pcm16_to_float32(pcm: bytes) -> np.ndarray:
    """Convert int16 PCM bytes to float32 waveform in [-1, 1]."""
    if not pcm:
        return np.zeros(0, dtype=np.float32)
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return samples / 32768.0


def float32_to_pcm16(wave: np.ndarray) -> bytes:
    clipped = np.clip(wave, -1.0, 1.0)
    return (clipped * 32767.0).astype(np.int16).tobytes()


def estimate_snr_db(wave: np.ndarray, *, noise_head_s: float, sample_rate: int) -> float:
    """Estimate SNR using the first ``noise_head_s`` as a noise floor."""
    if wave.size == 0:
        return 0.0
    head = max(1, int(noise_head_s * sample_rate))
    noise = wave[: min(head, wave.size)]
    noise_power = float(np.mean(noise**2)) + 1e-10
    signal_power = float(np.mean(wave**2)) + 1e-10
    return 10.0 * np.log10(signal_power / noise_power)


class PhoneAudioPreprocessor:
    """Normalize and denoise narrowband phone-call audio."""

    def __init__(self, config: KenyanAccentConfig) -> None:
        self._config = config

    def process(self, wave: np.ndarray, sample_rate: int) -> tuple[np.ndarray, int, float]:
        """Return (waveform, sample_rate, snr_db)."""
        if wave.size == 0:
            return wave, sample_rate, 0.0

        import librosa

        cfg = self._config
        y = wave.astype(np.float32, copy=False)

        if sample_rate != cfg.target_sample_rate:
            y = librosa.resample(
                y, orig_sr=sample_rate, target_sr=cfg.target_sample_rate, res_type="kaiser_fast"
            )
            sample_rate = cfg.target_sample_rate

        y = self._spectral_gate(y, sample_rate)
        y = self._telephony_bandpass(y, sample_rate)
        y = librosa.effects.preemphasis(y, coef=0.97)
        y = self._normalize_rms(y, target_db=-20.0)
        snr = estimate_snr_db(y, noise_head_s=0.2, sample_rate=sample_rate)
        return y, sample_rate, snr

    def _spectral_gate(self, y: np.ndarray, sample_rate: int) -> np.ndarray:
        """Lightweight noise suppression for constant phone-line hiss."""
        import librosa

        n_fft = self._config.n_fft
        hop = self._config.hop_length
        stft = librosa.stft(y, n_fft=n_fft, hop_length=hop, win_length=self._config.win_length)
        mag = np.abs(stft)
        noise_frames = max(1, int(0.2 * sample_rate / hop))
        noise_profile = np.median(mag[:, :noise_frames], axis=1, keepdims=True)
        floor = noise_profile * 1.5
        gated = np.maximum(mag - floor, 0.0)
        return librosa.istft(gated * np.exp(1j * np.angle(stft)), hop_length=hop, win_length=self._config.win_length)

    def _telephony_bandpass(self, y: np.ndarray, sample_rate: int) -> np.ndarray:
        from scipy.signal import butter, sosfilt

        cfg = self._config
        nyq = sample_rate * 0.5
        low = max(cfg.telephony_low_hz / nyq, 0.001)
        high = min(cfg.telephony_high_hz / nyq, 0.999)
        if low >= high:
            return y
        sos = butter(4, [low, high], btype="band", output="sos")
        return sosfilt(sos, y).astype(np.float32)

    def _normalize_rms(self, y: np.ndarray, *, target_db: float) -> np.ndarray:
        rms = float(np.sqrt(np.mean(y**2)) + 1e-10)
        target = 10 ** (target_db / 20.0)
        return np.clip(y * (target / rms), -1.0, 1.0)
