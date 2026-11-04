"""Factory for Kenyan conversational behavior."""

from __future__ import annotations

from dataclasses import replace

from api.services.kenyan_conversation.behavior import KenyanConversationBehavior
from api.services.kenyan_conversation.config import KenyanConversationConfig
from api.services.kenyan_conversation.types import LanguageMode


def create_kenyan_conversation_config(**overrides) -> KenyanConversationConfig:
    base = KenyanConversationConfig()
    if not overrides:
        return base
    if "language_mode" in overrides and isinstance(overrides["language_mode"], str):
        overrides = {**overrides, "language_mode": LanguageMode(overrides["language_mode"])}
    return replace(base, **overrides)


def create_kenyan_conversation_behavior(**overrides) -> KenyanConversationBehavior:
    return KenyanConversationBehavior(create_kenyan_conversation_config(**overrides))


def resolve_system_prompt(
    custom_prompt: str = "",
    *,
    domain: str = "general",
    language_mode: str = "mixed",
) -> str:
    """Build Kenyan behavior system prompt, merging custom instructions."""
    behavior = create_kenyan_conversation_behavior(
        domain=domain,
        language_mode=language_mode,
        enabled=True,
    )
    return behavior.system_prompt(custom_instructions=custom_prompt)
