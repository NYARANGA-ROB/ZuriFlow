"""Async integration hooks for the voice pipeline and telephony stack."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from api.services.kenyan_accent.service import KenyanAccentInferenceService, get_kenyan_accent_service
from api.services.kenyan_accent.types import AccentClass, AccentPrediction


AccentCallback = Callable[[AccentPrediction], Awaitable[None]]


@dataclass
class KenyanAccentHook:
    """Push inbound call audio through accent detection during a live session."""

    service: KenyanAccentInferenceService = field(default_factory=get_kenyan_accent_service)
    on_prediction: AccentCallback | None = None
    on_stable_kenyan: AccentCallback | None = None
    on_stable_generic: AccentCallback | None = None
    min_confidence: float = 0.55

    _session_id: str | None = field(default=None, init=False)
    _call_id: str | None = field(default=None, init=False)
    _started: bool = field(default=False, init=False)

    async def on_call_started(
        self,
        *,
        call_id: str,
        sample_rate: int = 16000,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        _ = metadata
        self._call_id = call_id
        self._session_id = await self.service.start_session(sample_rate=sample_rate)
        self._started = True
        logger.debug(
            "Kenyan accent hook started call_id={} session_id={}",
            call_id,
            self._session_id[:8],
        )
        return self._session_id

    async def on_inbound_audio(
        self,
        pcm: bytes,
        *,
        sample_rate: int = 16000,
    ) -> AccentPrediction | None:
        if not self._started or self._session_id is None:
            return None
        prediction = await self.service.push_chunk(
            self._session_id, pcm, sample_rate=sample_rate
        )
        if prediction is None:
            return None
        await self._dispatch(prediction)
        return prediction

    async def on_call_ended(self) -> AccentPrediction | None:
        if self._session_id is None:
            return None
        final = await self.service.end_session(self._session_id)
        self._started = False
        self._session_id = None
        if final is not None:
            await self._dispatch(final)
        return final

    async def _dispatch(self, prediction: AccentPrediction) -> None:
        if prediction.confidence < self.min_confidence:
            return
        if self.on_prediction is not None:
            await self.on_prediction(prediction)
        if prediction.is_stable and prediction.label == AccentClass.KENYAN_ENGLISH:
            if self.on_stable_kenyan is not None:
                await self.on_stable_kenyan(prediction)
        if prediction.is_stable and prediction.label == AccentClass.GENERIC_ENGLISH:
            if self.on_stable_generic is not None:
                await self.on_stable_generic(prediction)


@dataclass
class KenyanAccentHookRegistry:
    """Global registry for attaching accent hooks to active calls."""

    _hooks: dict[str, KenyanAccentHook] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def attach(self, call_id: str, hook: KenyanAccentHook) -> None:
        async with self._lock:
            self._hooks[call_id] = hook

    async def detach(self, call_id: str) -> KenyanAccentHook | None:
        async with self._lock:
            return self._hooks.pop(call_id, None)

    async def get(self, call_id: str) -> KenyanAccentHook | None:
        async with self._lock:
            return self._hooks.get(call_id)

    async def feed_audio(
        self, call_id: str, pcm: bytes, *, sample_rate: int = 16000
    ) -> AccentPrediction | None:
        hook = await self.get(call_id)
        if hook is None:
            return None
        return await hook.on_inbound_audio(pcm, sample_rate=sample_rate)


_registry: KenyanAccentHookRegistry | None = None


def get_kenyan_accent_hook_registry() -> KenyanAccentHookRegistry:
    global _registry
    if _registry is None:
        _registry = KenyanAccentHookRegistry()
    return _registry
