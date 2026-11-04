"""Integration helpers for telephony and voice pipeline callers."""

from __future__ import annotations

from typing import Any

from api.constants import KENYAN_ACCENT_ENABLED
from api.services.kenyan_accent.factory import create_kenyan_accent_hook
from api.services.kenyan_accent.hooks import KenyanAccentHook, get_kenyan_accent_hook_registry
from api.services.kenyan_accent.types import AccentPrediction


async def attach_kenyan_accent_to_call(
    call_id: str,
    *,
    sample_rate: int = 16000,
    on_stable_kenyan: Any = None,
    on_stable_generic: Any = None,
) -> KenyanAccentHook | None:
    """Attach accent detection to an active phone call.

    Call ``feed_call_audio`` from your inbound audio path (STT tap, recording, etc.).
    """
    if not KENYAN_ACCENT_ENABLED:
        return None

    hook = create_kenyan_accent_hook()
    if on_stable_kenyan is not None:
        hook.on_stable_kenyan = on_stable_kenyan
    if on_stable_generic is not None:
        hook.on_stable_generic = on_stable_generic

    await get_kenyan_accent_hook_registry().attach(call_id, hook)
    await hook.on_call_started(call_id=call_id, sample_rate=sample_rate)
    return hook


async def feed_call_audio(
    call_id: str,
    pcm: bytes,
    *,
    sample_rate: int = 16000,
) -> AccentPrediction | None:
    """Push inbound telephony PCM into the accent hook for ``call_id``."""
    return await get_kenyan_accent_hook_registry().feed_audio(
        call_id, pcm, sample_rate=sample_rate
    )


async def detach_kenyan_accent_from_call(call_id: str) -> AccentPrediction | None:
    """Stop accent detection and return the final prediction for a call."""
    registry = get_kenyan_accent_hook_registry()
    hook = await registry.detach(call_id)
    if hook is None:
        return None
    return await hook.on_call_ended()
