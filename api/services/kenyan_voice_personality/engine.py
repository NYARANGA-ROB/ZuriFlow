"""Kenyan voice personality runtime engine."""

from __future__ import annotations

from api.services.kenyan_conversation.behavior import KenyanConversationBehavior
from api.services.kenyan_conversation.factory import create_kenyan_conversation_config
from api.services.kenyan_conversation.types import TurnContext
from api.services.kenyan_voice_personality.middleware import (
    KenyanVoicePersonalityMiddleware,
    KenyanVoicePersonalityTextFilter,
)
from api.services.kenyan_voice_personality.playback import PlaybackAdaptationLayer, PlaybackPlan
from api.services.kenyan_voice_personality.resolver import get_voice_personality_resolver
from api.services.kenyan_voice_personality.schema import ResolvedVoicePersonality, ToneConfiguration


class KenyanVoicePersonalityEngine:
    """Orchestrates tone, TTS shaping, and interruption-aware playback."""

    def __init__(self, resolved: ResolvedVoicePersonality) -> None:
        self.resolved = resolved
        conv_cfg = create_kenyan_conversation_config(
            enabled=True,
            **resolved.conversation_config_overrides,
        )
        self.behavior = KenyanConversationBehavior(conv_cfg)
        self.middleware = KenyanVoicePersonalityMiddleware(resolved)
        self.playback = PlaybackAdaptationLayer(resolved)
        self._text_filter = KenyanVoicePersonalityTextFilter(resolved)

    @classmethod
    async def from_profile(
        cls,
        profile_id: str,
        *,
        organization_id: int | None = None,
        tone: ToneConfiguration | None = None,
    ) -> KenyanVoicePersonalityEngine:
        resolved = await get_voice_personality_resolver().resolve(
            profile_id,
            organization_id=organization_id,
            tone_override=tone,
        )
        return cls(resolved)

    def system_prompt(self, *, custom_instructions: str = "") -> str:
        overlay = self.resolved.profile.system_prompt_overlay
        merged = f"{overlay}\n\n{custom_instructions}".strip() if custom_instructions else overlay
        return self.behavior.system_prompt(custom_instructions=merged)

    def begin_turn(self, *, was_interrupted: bool = False, partial_spoken: str = "") -> TurnContext:
        self._text_filter.set_interrupted(was_interrupted)
        return self.behavior.begin_turn(
            was_interrupted=was_interrupted,
            partial_spoken=partial_spoken,
        )

    def process_response(self, text: str, ctx: TurnContext) -> tuple[str, PlaybackPlan]:
        styled = self.behavior.transform_response(text, ctx)
        tts_ready = self.middleware.transform_for_tts(
            styled, was_interrupted=ctx.was_interrupted
        )
        plan = self.playback.plan_turn(tts_ready, ctx=ctx)
        return tts_ready, plan

    def pipecat_text_filter(self) -> KenyanVoicePersonalityTextFilter:
        return self._text_filter

    def tts_mapping(self) -> dict:
        mapping = self.resolved.profile.tts_mapping
        return {
            **mapping.to_dict(),
            "speed": self.resolved.effective_speed,
        }


async def create_personality_engine(
    profile_id: str,
    *,
    organization_id: int | None = None,
    tone: ToneConfiguration | None = None,
) -> KenyanVoicePersonalityEngine:
    return await KenyanVoicePersonalityEngine.from_profile(
        profile_id,
        organization_id=organization_id,
        tone=tone,
    )
