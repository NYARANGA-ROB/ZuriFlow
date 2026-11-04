"""Factory for Kenyan accent detection components."""

from __future__ import annotations

from dataclasses import replace

from api.constants import KENYAN_ACCENT_ENABLED, KENYAN_ACCENT_MODEL_PATH, PYANNOTE_AUTH_TOKEN
from api.services.kenyan_accent.config import KenyanAccentConfig
from api.services.kenyan_accent.hooks import KenyanAccentHook
from api.services.kenyan_accent.service import KenyanAccentInferenceService


def create_kenyan_accent_config(**overrides) -> KenyanAccentConfig:
    base = KenyanAccentConfig(
        enabled=KENYAN_ACCENT_ENABLED,
        model_path=KENYAN_ACCENT_MODEL_PATH,
        pyannote_token=PYANNOTE_AUTH_TOKEN,
    )
    if not overrides:
        return base
    return replace(base, **overrides)


def create_kenyan_accent_service(**config_overrides) -> KenyanAccentInferenceService:
    return KenyanAccentInferenceService(create_kenyan_accent_config(**config_overrides))


def create_kenyan_accent_hook(**config_overrides) -> KenyanAccentHook:
    return KenyanAccentHook(service=create_kenyan_accent_service(**config_overrides))
