"""Lightweight PyTorch accent classifier (generic vs Kenyan English)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from loguru import logger

from api.services.kenyan_accent.config import KenyanAccentConfig
from api.services.kenyan_accent.features import AccentFeatureExtractor, AccentFeatures
from api.services.kenyan_accent.types import AccentClass, AccentScores


class _MelAccentNet(nn.Module):
    """Small CNN + MLP for realtime phone-accent discrimination."""

    def __init__(self, n_mels: int, vector_dim: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4)),
        )
        self.mlp = nn.Sequential(
            nn.Linear(32 * 4 * 4 + vector_dim, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.15),
            nn.Linear(128, 2),
        )

    def forward(self, mel: torch.Tensor, stats: torch.Tensor) -> torch.Tensor:
        x = self.conv(mel)
        x = x.flatten(1)
        x = torch.cat([x, stats], dim=1)
        return self.mlp(x)


class AccentClassifier:
    """Binary classifier: generic English vs Kenyan English."""

    def __init__(self, config: KenyanAccentConfig, extractor: AccentFeatureExtractor) -> None:
        self._config = config
        self._extractor = extractor
        self._device = torch.device(config.device)
        vector_dim = config.n_mfcc * 2 + config.n_mels * 2 + 1
        self._model = _MelAccentNet(config.n_mels, vector_dim).to(self._device)
        self._model.eval()
        self._weights_loaded = False
        self._load_weights()

    @property
    def weights_loaded(self) -> bool:
        return self._weights_loaded

    def _load_weights(self) -> None:
        path = self._config.model_path
        if not path:
            logger.info(
                "Kenyan accent: no KENYAN_ACCENT_MODEL_PATH — using initialized weights"
            )
            return
        model_path = Path(path)
        if not model_path.exists():
            logger.warning("Kenyan accent model not found at {}", path)
            return
        try:
            state = torch.load(model_path, map_location=self._device, weights_only=True)
            self._model.load_state_dict(state)
            self._weights_loaded = True
            logger.info("Kenyan accent model loaded from {}", path)
        except Exception as e:
            logger.warning("Failed to load Kenyan accent model: {}", e)

    def predict(self, features: AccentFeatures) -> AccentScores:
        with torch.inference_mode():
            mel = features.mel_spectrogram.to(self._device)
            stats = self._extractor.vectorize(features).unsqueeze(0).to(self._device)
            logits = self._model(mel, stats)
            probs = F.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

        if not self._weights_loaded:
            probs = self._heuristic_scores(features)

        return AccentScores(
            generic_english=float(probs[0]),
            kenyan_english=float(probs[1]),
        )

    def _heuristic_scores(self, features: AccentFeatures) -> np.ndarray:
        """Acoustic prior when no trained checkpoint is available.

        Kenyan English on phone lines often shows higher spectral tilt in mid
        frequencies, stronger F2-region energy, and slightly higher syllable-rate
        variability. This is a weak prior — replace with a trained model for prod.
        """
        mel = features.mel_mean
        mfcc = features.mfcc_mean
        mid_band = float(np.mean(mel[16:40])) if mel.size else 0.0
        low_band = float(np.mean(mel[:16])) if mel.size else 0.0
        mfcc_var = float(np.std(mfcc)) if mfcc.size else 0.0

        kenyan_score = (
            0.35 * np.tanh((mid_band - low_band) * 2.0)
            + 0.25 * np.tanh(mfcc_var * 0.5)
            + 0.15 * features.speech_ratio
        )
        kenyan_prob = float(np.clip(0.5 + kenyan_score, 0.05, 0.95))
        return np.array([1.0 - kenyan_prob, kenyan_prob], dtype=np.float32)

    @staticmethod
    def entropy(scores: AccentScores) -> float:
        p = np.array([scores.generic_english, scores.kenyan_english], dtype=np.float64)
        p = np.clip(p, 1e-8, 1.0)
        p = p / p.sum()
        return float(-np.sum(p * np.log(p)))
