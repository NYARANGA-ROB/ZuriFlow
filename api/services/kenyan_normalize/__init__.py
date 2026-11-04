"""Kenyan language normalization — Sheng, Swahili, and code-switching to structured English."""

from api.services.kenyan_normalize.config import (
    DEFAULT_KENYAN_NORMALIZE_CONFIG,
    KenyanNormalizeConfig,
)
from api.services.kenyan_normalize.dictionary.manager import SlangDictionaryManager
from api.services.kenyan_normalize.service import KenyanNormalizeService, get_kenyan_normalize_service
from api.services.kenyan_normalize.types import NormalizeResult

__all__ = [
    "DEFAULT_KENYAN_NORMALIZE_CONFIG",
    "KenyanNormalizeConfig",
    "KenyanNormalizeService",
    "NormalizeResult",
    "SlangDictionaryManager",
    "get_kenyan_normalize_service",
]
