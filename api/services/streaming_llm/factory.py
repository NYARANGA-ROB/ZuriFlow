"""Factory for streaming LLM response engine."""

from __future__ import annotations

from dataclasses import replace

from api.services.streaming_llm.config import StreamingLLMConfig, DEFAULT_STREAMING_LLM_CONFIG
from api.services.streaming_llm.engine import StreamingLLMResponseEngine
from api.services.voice_pipeline.llm.streaming_adapter import StreamingLLMBridge


def create_streaming_llm_engine(
    *,
    api_key: str,
    model: str | None = None,
    config: StreamingLLMConfig | None = None,
) -> StreamingLLMResponseEngine:
    base = config or DEFAULT_STREAMING_LLM_CONFIG
    if model:
        base = replace(base, model=model)
    return StreamingLLMResponseEngine(api_key=api_key, config=base)


def create_streaming_llm_bridge(
    *,
    api_key: str,
    model: str | None = None,
    config: StreamingLLMConfig | None = None,
) -> StreamingLLMBridge:
    engine = create_streaming_llm_engine(api_key=api_key, model=model, config=config)
    return StreamingLLMBridge(engine)
