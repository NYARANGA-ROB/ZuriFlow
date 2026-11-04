"""Pipecat-backed media transport adapter."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from api.services.pipecat.audio_config import create_audio_config
from api.services.telephony import registry as telephony_registry
from api.services.voice_pipeline.streaming.interfaces import (
    AudioInbound,
    AudioOutbound,
    MediaTransport,
)
from api.services.voice_pipeline.types import AudioChunk, VoicePipelineConfig


class _QueueInbound:
    def __init__(self, queue: asyncio.Queue[AudioChunk | None]):
        self._queue = queue

    async def audio_chunks(self) -> AsyncIterator[AudioChunk]:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item


class _QueueOutbound:
    def __init__(self, queue: asyncio.Queue[AudioChunk | None]):
        self._queue = queue

    async def send(self, chunk: AudioChunk) -> None:
        await self._queue.put(chunk)


class PipecatMediaTransport:
    """Bridges the modular pipeline to Pipecat ``FastAPIWebsocketTransport``.

    The orchestrator uses queue-based inbound/outbound for modular services;
    ``attach_pipecat_transport`` connects the live Pipecat transport when
    running in bridge mode.
    """

    def __init__(self) -> None:
        self._in_queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self._out_queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self._pipecat_transport: Any = None
        self._config: VoicePipelineConfig | None = None

    async def open(
        self,
        config: VoicePipelineConfig,
        websocket: Any,
        *,
        transport_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._config = config
        audio_config = create_audio_config(config.provider_name)
        spec = telephony_registry.get(config.provider_name)

        workflow = None
        ambient_noise_config = None
        from api.db import db_client

        workflow = await db_client.get_workflow(
            config.workflow_id, config.user_id
        )
        if workflow and workflow.workflow_configurations:
            ambient_noise_config = workflow.workflow_configurations.get(
                "ambient_noise_configuration"
            )

        self._pipecat_transport = await spec.transport_factory(
            websocket,
            config.workflow_run_id,
            audio_config,
            config.organization_id,
            ambient_noise_config=ambient_noise_config,
            telephony_configuration_id=config.telephony_configuration_id,
            is_realtime=config.is_realtime,
            **(transport_kwargs or {}),
        )
        logger.debug(
            f"Pipecat transport opened for run {config.workflow_run_id} "
            f"provider={config.provider_name}"
        )

    @property
    def pipecat_transport(self) -> Any:
        if self._pipecat_transport is None:
            raise RuntimeError("MediaTransport.open() not called")
        return self._pipecat_transport

    async def close(self) -> None:
        await self._in_queue.put(None)
        await self._out_queue.put(None)
        self._pipecat_transport = None

    def inbound(self) -> AudioInbound:
        return _QueueInbound(self._in_queue)

    def outbound(self) -> AudioOutbound:
        return _QueueOutbound(self._out_queue)


class InMemoryMediaTransport:
    """Example transport for tests and local echo pipelines."""

    def __init__(self) -> None:
        self._in_queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self._out_queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()

    async def open(
        self,
        config: VoicePipelineConfig,
        websocket: Any = None,
        **kwargs: Any,
    ) -> None:
        _ = config, websocket, kwargs

    async def close(self) -> None:
        await self._in_queue.put(None)
        await self._out_queue.put(None)

    def inbound(self) -> AudioInbound:
        return _QueueInbound(self._in_queue)

    def outbound(self) -> AudioOutbound:
        return _QueueOutbound(self._out_queue)

    async def inject_audio(self, chunk: AudioChunk) -> None:
        await self._in_queue.put(chunk)

    async def drain_output(self) -> AsyncIterator[AudioChunk]:
        while True:
            item = await self._out_queue.get()
            if item is None:
                break
            yield item
