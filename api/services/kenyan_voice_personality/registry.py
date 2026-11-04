"""Voice profile registry with search."""

from __future__ import annotations

from api.services.kenyan_voice_personality.profiles import BUILTIN_PROFILES
from api.services.kenyan_voice_personality.schema import KenyanVoiceProfile, KenyanVoiceStyle


class KenyanVoiceProfileRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, KenyanVoiceProfile] = {}

    def register(self, profile: KenyanVoiceProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> KenyanVoiceProfile | None:
        return self._profiles.get(profile_id)

    def require(self, profile_id: str) -> KenyanVoiceProfile:
        profile = self.get(profile_id)
        if profile is None:
            raise KeyError(f"Voice profile not found: {profile_id}")
        return profile

    def get_by_style(self, style: KenyanVoiceStyle) -> KenyanVoiceProfile | None:
        for p in self._profiles.values():
            if p.style == style:
                return p
        return None

    def list_profiles(self) -> list[KenyanVoiceProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.name)

    def search(
        self,
        *,
        q: str = "",
        tag: str | None = None,
        domain: str | None = None,
        locale: str | None = None,
        limit: int = 20,
    ) -> list[KenyanVoiceProfile]:
        items = self.list_profiles()
        query = q.strip().lower()

        def matches(p: KenyanVoiceProfile) -> bool:
            if tag and tag not in p.tags:
                return False
            if domain and p.domain != domain:
                return False
            if locale and locale not in p.multilingual.supported_locales:
                return False
            if not query:
                return True
            haystack = " ".join(
                [p.profile_id, p.name, p.description, *p.tags, *p.search_keywords]
            ).lower()
            return query in haystack or any(w in haystack for w in query.split())

        return [p for p in items if matches(p)][:limit]


_registry: KenyanVoiceProfileRegistry | None = None


def get_kenyan_voice_profile_registry() -> KenyanVoiceProfileRegistry:
    global _registry
    if _registry is None:
        _registry = KenyanVoiceProfileRegistry()
        for profile in BUILTIN_PROFILES:
            _registry.register(profile)
    return _registry
