"""Acoustic feature extraction with librosa and torchaudio."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from api.services.kenyan_accent.config import KenyanAccentConfig


@dataclass(frozen=True)
class AccentFeatures:
    """Pooled acoustic features for the accent classifier."""

    mfcc_mean: np.ndarray
    mfcc_std: np.ndarray
    mel_mean: np.ndarray
    mel_std: np.ndarray
    mel_spectrogram: torch.Tensor
    speech_ratio: float


class AccentFeatureExtractor:
    """Extract MFCC and mel features optimized for narrowband speech."""

    def __init__(self, config: KenyanAccentConfig) -> None:
        self._config = config
        import torchaudio.transforms as T

        cfg = config
        self._mel_transform = T.MelSpectrogram(
            sample_rate=cfg.target_sample_rate,
            n_fft=cfg.n_fft,
            hop_length=cfg.hop_length,
            win_length=cfg.win_length,
            n_mels=cfg.n_mels,
            power=2.0,
        )
        self._amplitude_to_db = T.AmplitudeToDB(stype="power", top_db=80.0)

    def extract(
        self,
        wave: np.ndarray,
        sample_rate: int,
        *,
        speech_mask: np.ndarray | None = None,
    ) -> AccentFeatures:
        import librosa

        cfg = self._config
        y = wave.astype(np.float32, copy=False)

        mfcc = librosa.feature.mfcc(
            y=y,
            sr=sample_rate,
            n_mfcc=cfg.n_mfcc,
            n_fft=cfg.n_fft,
            hop_length=cfg.hop_length,
            win_length=cfg.win_length,
        )

        tensor = torch.from_numpy(y).unsqueeze(0)
        mel = self._amplitude_to_db(self._mel_transform(tensor)).squeeze(0).numpy()

        if speech_mask is not None and speech_mask.shape == mfcc.shape[1:]:
            cols = speech_mask.astype(bool)
            if cols.any():
                mfcc = mfcc[:, cols]
                mel = mel[:, cols]

        speech_ratio = 1.0
        if speech_mask is not None and speech_mask.size:
            speech_ratio = float(np.mean(speech_mask))

        return AccentFeatures(
            mfcc_mean=np.mean(mfcc, axis=1),
            mfcc_std=np.std(mfcc, axis=1),
            mel_mean=np.mean(mel, axis=1),
            mel_std=np.std(mel, axis=1),
            mel_spectrogram=torch.from_numpy(mel).unsqueeze(0).unsqueeze(0).float(),
            speech_ratio=speech_ratio,
        )

    def vectorize(self, features: AccentFeatures) -> torch.Tensor:
        """Flatten pooled statistics into a fixed-length vector."""
        parts = [
            features.mfcc_mean,
            features.mfcc_std,
            features.mel_mean,
            features.mel_std,
            np.array([features.speech_ratio], dtype=np.float32),
        ]
        return torch.from_numpy(np.concatenate(parts)).float()
