"""Kenyan English accent detection for telephony audio."""

from api.services.kenyan_accent.config import KenyanAccentConfig, DEFAULT_KENYAN_ACCENT_CONFIG
from api.services.kenyan_accent.hooks import KenyanAccentHook, KenyanAccentHookRegistry
from api.services.kenyan_accent.service import KenyanAccentInferenceService
from api.services.kenyan_accent.types import AccentClass, AccentPrediction

__all__ = [
    "AccentClass",
    "AccentPrediction",
    "DEFAULT_KENYAN_ACCENT_CONFIG",
    "KenyanAccentConfig",
    "KenyanAccentHook",
    "KenyanAccentHookRegistry",
    "KenyanAccentInferenceService",
]
