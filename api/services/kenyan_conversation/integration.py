"""Integration with the realtime voice pipeline."""

from __future__ import annotations

from functools import lru_cache

from api.constants import KENYAN_CONVERSATION_ENABLED
from api.services.kenyan_conversation.behavior import KenyanConversationBehavior
from api.services.kenyan_conversation.factory import create_kenyan_conversation_behavior


def get_kenyan_conversation_behavior(
    *,
    domain: str = "general",
    language_mode: str | None = None,
) -> KenyanConversationBehavior | None:
    if not KENYAN_CONVERSATION_ENABLED:
        return None
    kwargs: dict = {"enabled": True, "domain": domain}
    if language_mode:
        kwargs["language_mode"] = language_mode
    return create_kenyan_conversation_behavior(**kwargs)


def merge_system_prompt(
    base_prompt: str = "",
    *,
    domain: str = "general",
    language_mode: str = "mixed",
) -> str:
    """Return Kenyan behavior prompt layered with caller-specific instructions."""
    return _merged_prompt(base_prompt, domain, language_mode)


@lru_cache(maxsize=256)
def _merged_prompt(base_prompt: str, domain: str, language_mode: str) -> str:
    behavior = create_kenyan_conversation_behavior(
        enabled=True,
        domain=domain,
        language_mode=language_mode,
    )
    return behavior.system_prompt(custom_instructions=base_prompt)
