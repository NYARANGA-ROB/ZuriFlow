"""Factory for Kenyan language normalization."""

from __future__ import annotations

from dataclasses import replace

from api.services.kenyan_normalize.config import KenyanNormalizeConfig
from api.services.kenyan_normalize.service import KenyanNormalizeService


def create_kenyan_normalize_config(**overrides) -> KenyanNormalizeConfig:
    base = KenyanNormalizeConfig()
    if not overrides:
        return base
    return replace(base, **overrides)


def create_kenyan_normalize_service(**overrides) -> KenyanNormalizeService:
    return KenyanNormalizeService(create_kenyan_normalize_config(**overrides))
