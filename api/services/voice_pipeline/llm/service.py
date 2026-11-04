"""LLM service implementations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from api.services.pipecat.audio_config import AudioConfig
from api.services.pipecat.service_factory import (
    create_llm_service,
    create_realtime_llm_service,
)
from api.services.voice_pipeline.llm.interfaces import LLMService, RealtimeLLMService
from api.services.voice_pipeline.types import LLMMessage, LLMStreamEvent, LLMStreamKind


class PipecatLLMAdapter:
    """Factory wrapper — generation runs through Pipecat frame processors in bridge mode."""

    def __init__(
        self,
        *,
        user_config: object,
        correlation_id: str | None = None,
    ) -> None:
        self._user_config = user_config
        self._correlation_id = correlation_id
        self._llm = None
        self._system_prompt = ""

    async def start(self) -> None:
        self._llm = create_llm_service(
            self._user_config, correlation_id=self._correlation_id
        )

    async def stop(self) -> None:
        self._llm = None

    async def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    async def generate(
        self, messages: list[LLMMessage], *, tools: list[dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMStreamEvent]:
        _ = messages, tools
        if self._llm is None:
            raise RuntimeError("PipecatLLMAdapter.start() not called")
        yield LLMStreamEvent(
            kind=LLMStreamKind.TEXT_DONE,
            text="[pipecat bridge: use LegacyVoiceOrchestrator for production LLM]",
        )


class PipecatRealtimeLLMAdapter:
    """Wraps create_realtime_llm_service for DI containers."""

    def __init__(self, *, user_config: object, audio_config: AudioConfig) -> None:
        self._user_config = user_config
        self._audio_config = audio_config
        self._llm = None

    async def start(self) -> None:
        self._llm = create_realtime_llm_service(self._user_config, self._audio_config)
        logger.debug("PipecatRealtimeLLMAdapter started")

    async def stop(self) -> None:
        self._llm = None

    async def set_system_prompt(self, prompt: str) -> None:
        if self._llm is not None and hasattr(self._llm, "_update_settings"):
            from pipecat.services.settings import LLMSettings

            await self._llm._update_settings(LLMSettings(system_instruction=prompt))

    @property
    def pipecat_service(self) -> Any:
        return self._llm


class EchoLLMService:
    """Example LLM that parrots the last user message."""

    def __init__(self, *, prefix: str = "You said: ") -> None:
        self._prefix = prefix
        self._system_prompt = ""

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    async def generate(
        self, messages: list[LLMMessage], *, tools: list[dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMStreamEvent]:
        _ = tools
        user_text = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_text = msg.content
                break
        response = f"{self._prefix}{user_text}"
        for word in response.split():
            await asyncio.sleep(0.01)
            yield LLMStreamEvent(kind=LLMStreamKind.TEXT_DELTA, text=word + " ")
        yield LLMStreamEvent(kind=LLMStreamKind.TEXT_DONE, text=response)
