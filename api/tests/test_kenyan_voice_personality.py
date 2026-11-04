"""Tests for Kenyan voice personality system."""

from __future__ import annotations

import pytest

from api.services.kenyan_voice_personality.engine import KenyanVoicePersonalityEngine
from api.services.kenyan_voice_personality.middleware import KenyanVoicePersonalityMiddleware
from api.services.kenyan_voice_personality.playback import PlaybackAdaptationLayer
from api.services.kenyan_voice_personality.profiles import SACCO_COLLECTIONS_OFFICER
from api.services.kenyan_voice_personality.registry import get_kenyan_voice_profile_registry
from api.services.kenyan_voice_personality.schema import EmotionalTone, ToneConfiguration
from api.services.kenyan_voice_personality.tone import get_tone_configuration_system
from api.services.kenyan_conversation.types import TurnContext


@pytest.fixture(autouse=True)
def _init_registry():
    get_kenyan_voice_profile_registry()


class TestRegistry:
    def test_four_builtin_profiles(self):
        registry = get_kenyan_voice_profile_registry()
        ids = {p.profile_id for p in registry.list_profiles()}
        assert ids == {
            "nairobi_professional",
            "friendly_receptionist",
            "sacco_collections_officer",
            "logistics_dispatcher",
        }

    def test_search_sacco(self):
        registry = get_kenyan_voice_profile_registry()
        results = registry.search(q="sacco")
        assert len(results) == 1
        assert results[0].profile_id == "sacco_collections_officer"


class TestToneSystem:
    def test_urgency_increases_speed(self):
        system = get_tone_configuration_system()
        base = system.resolve(SACCO_COLLECTIONS_OFFICER)
        urgent = system.resolve(
            SACCO_COLLECTIONS_OFFICER,
            ToneConfiguration(emotional_tone=EmotionalTone.URGENT, urgency=0.9),
        )
        assert urgent.effective_speed > base.effective_speed


class TestMiddleware:
    def test_interrupt_acknowledgement(self):
        system = get_tone_configuration_system()
        resolved = system.resolve(SACCO_COLLECTIONS_OFFICER)
        mw = KenyanVoicePersonalityMiddleware(resolved)
        out = mw.transform_for_tts("Please pay your balance.", was_interrupted=True)
        assert out.lower().startswith("sawa") or out.lower().startswith("okay")

    def test_register_casual_transform(self):
        registry = get_kenyan_voice_profile_registry()
        profile = registry.require("friendly_receptionist")
        resolved = get_tone_configuration_system().resolve(profile)
        mw = KenyanVoicePersonalityMiddleware(resolved)
        out = mw.transform_for_tts("Certainly, I can help with that.")
        assert "Certainly" not in out


class TestPlayback:
    def test_interrupt_truncates_long_chunks(self):
        resolved = get_tone_configuration_system().resolve(SACCO_COLLECTIONS_OFFICER)
        layer = PlaybackAdaptationLayer(resolved)
        long_text = " ".join(["word"] * 30) + "."
        plan = layer.plan_turn(long_text, ctx=TurnContext(was_interrupted=True))
        assert len(plan.chunks) >= 1
        assert len(plan.chunks[0].text.split()) <= 9

    def test_pause_before_resume_after_interrupt(self):
        resolved = get_tone_configuration_system().resolve(SACCO_COLLECTIONS_OFFICER)
        layer = PlaybackAdaptationLayer(resolved)
        plan = layer.plan_turn("Sawa, tunaendelea.", ctx=TurnContext(was_interrupted=True))
        assert plan.pause_before_ms > 0


class TestEngine:
    @pytest.mark.asyncio
    async def test_process_response_pipeline(self):
        engine = await KenyanVoicePersonalityEngine.from_profile("logistics_dispatcher")
        ctx = engine.begin_turn()
        text = "Certainly, the driver is on the way to your location now."
        tts_ready, plan = engine.process_response(text, ctx)
        assert "Certainly" not in tts_ready
        assert len(plan.chunks) >= 1
        assert plan.speed_multiplier > 1.0
