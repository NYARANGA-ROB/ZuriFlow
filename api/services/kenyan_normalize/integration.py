"""Integration helpers — normalize STT transcripts before LLM routing."""

from __future__ import annotations

from api.constants import KENYAN_NORMALIZE_ENABLED
from api.services.kenyan_normalize.service import get_kenyan_normalize_service
from api.services.kenyan_normalize.types import NormalizeResult


def normalize_transcript(text: str) -> NormalizeResult:
    """Normalize a caller transcript (sync, for STT final hooks)."""
    if not KENYAN_NORMALIZE_ENABLED:
        return NormalizeResult(original=text, normalized=text)
    return get_kenyan_normalize_service().normalize(text)


async def normalize_transcript_async(text: str) -> NormalizeResult:
    """Async wrapper for pipeline handlers."""
    return normalize_transcript(text)
