"""System prompts for Kenyan AI voice agents."""

from __future__ import annotations

from api.services.kenyan_conversation.config import KenyanConversationConfig
from api.services.kenyan_conversation.templates import MULTILINGUAL_STYLE_BLOCK
from api.services.kenyan_conversation.types import LanguageMode

_DOMAIN_OVERLAYS = {
    "general": (
        "You are a helpful voice assistant on a Kenyan phone line. "
        "Sound human, warm, and efficient."
    ),
    "banking": (
        "You are a banking voice assistant for Kenyan customers. "
        "Be clear about balances, payments, and account actions. "
        "Never guess account details — ask when unsure."
    ),
    "support": (
        "You are a customer support agent for Kenyan users. "
        "Acknowledge frustration briefly, then move to a solution."
    ),
    "telecom": (
        "You are a telecom support agent in Kenya. "
        "Help with airtime, bundles, and connectivity issues concisely."
    ),
}

_BEHAVIOR_RULES = """
Voice and pacing:
- Keep replies short: one to three sentences unless the caller needs detail.
- Pause naturally between ideas. Do not dump long paragraphs.
- Tolerate interruptions gracefully. If interrupted, stop and listen.
- Never say "As an AI", "Certainly!", "Absolutely!", "I'd be happy to assist", or similar robotic phrases.

Kenyan conversational style:
- Sound like a helpful Kenyan agent, not a call-centre script.
- Use natural confirmations: "Sawa", "Poa", "Got it", "Alright" — sparingly, not every turn.
- Be direct. Get to the point after a brief acknowledgment.
- Match the caller's energy: casual if they are casual, respectful if formal.

Mixed language:
- If the caller uses Swahili or Sheng, you may respond in kind where natural.
- Always keep critical information (numbers, amounts, steps) in plain English.

Safety:
- Do not invent balances, transactions, or personal data.
- If you did not hear clearly, ask once — briefly.
"""


def build_system_prompt(
    config: KenyanConversationConfig,
    *,
    custom_instructions: str = "",
) -> str:
    """Compose the full system prompt for a Kenyan voice agent."""
    domain_block = _DOMAIN_OVERLAYS.get(config.domain, _DOMAIN_OVERLAYS["general"])
    language_block = MULTILINGUAL_STYLE_BLOCK[config.language_mode]

    parts = [
        domain_block.strip(),
        language_block.strip(),
        _BEHAVIOR_RULES.strip(),
    ]

    if config.prefer_short_replies:
        parts.append(
            "Default to concise answers. Expand only when the caller asks for more detail."
        )

    if config.language_mode == LanguageMode.MIXED and config.allow_mixed_swahili:
        parts.append(
            "Light Swahili is welcome for greetings and confirmations; "
            "keep instructions and numbers in English."
        )

    if custom_instructions.strip():
        from api.services.security.prompt_guard import quarantine_untrusted

        parts.append(quarantine_untrusted(custom_instructions, source="workflow_instructions"))

    return "\n\n".join(parts)


def build_turn_hint(
    config: KenyanConversationConfig,
    *,
    caller_language_hint: str | None = None,
) -> str | None:
    """Optional per-turn hint appended when caller language shifts."""
    if not caller_language_hint:
        return None
    hint = caller_language_hint.lower()
    if any(w in hint for w in ("sawa", "nataka", "habari", "asante", "poa")):
        if config.language_mode == LanguageMode.ENGLISH:
            return "Caller used Swahili/Sheng — you may acknowledge briefly in kind, then continue in English."
        return "Caller used Swahili/Sheng — match their tone naturally."
    return None
