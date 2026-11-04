from api.services.streaming_llm.config import DEFAULT_STREAMING_LLM_CONFIG, StreamingLLMConfig

__all__ = [
    "ConversationMessage",
    "ConversationStateManager",
    "DEFAULT_STREAMING_LLM_CONFIG",
    "GenerationCancellationRegistry",
    "GenerationCancellationToken",
    "OpenAIRealtimeClient",
    "ResponseStreamEvent",
    "ResponseStreamKind",
    "StreamingLLMClient",
    "StreamingLLMConfig",
    "StreamingLLMResponseEngine",
    "TokenStreamingHandler",
    "create_streaming_llm_bridge",
    "create_streaming_llm_engine",
]


def __getattr__(name: str):
    if name in ("GenerationCancellationRegistry", "GenerationCancellationToken"):
        from api.services.streaming_llm.cancellation import (
            GenerationCancellationRegistry,
            GenerationCancellationToken,
        )

        return locals()[name]
    if name == "OpenAIRealtimeClient":
        from api.services.streaming_llm.clients.openai_realtime import OpenAIRealtimeClient

        return OpenAIRealtimeClient
    if name == "ConversationStateManager":
        from api.services.streaming_llm.conversation import ConversationStateManager

        return ConversationStateManager
    if name == "StreamingLLMResponseEngine":
        from api.services.streaming_llm.engine import StreamingLLMResponseEngine

        return StreamingLLMResponseEngine
    if name in ("create_streaming_llm_bridge", "create_streaming_llm_engine"):
        from api.services.streaming_llm import factory

        return getattr(factory, name)
    if name == "StreamingLLMClient":
        from api.services.streaming_llm.interfaces import StreamingLLMClient

        return StreamingLLMClient
    if name == "TokenStreamingHandler":
        from api.services.streaming_llm.tokens import TokenStreamingHandler

        return TokenStreamingHandler
    if name in ("ConversationMessage", "ResponseStreamEvent", "ResponseStreamKind"):
        from api.services.streaming_llm import types

        return getattr(types, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
