"""Per-call conversational intelligence session (code-switch + confidence streaks)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from api.services.kenya.config import KenyaLanguage
from api.services.kenya.language import LanguageGuess


@dataclass
class KenyaIntelligenceSession:
    session_id: str
    preferred_language: KenyaLanguage | None = None
    last_primary: KenyaLanguage | None = None
    switch_count: int = 0
    low_confidence_streak: int = 0
    clarification_count: int = 0
    failed_recognition_count: int = 0
    intent_success_count: int = 0
    turn_count: int = 0
    sheng_turns: int = 0
    last_intents: list[str] = field(default_factory=list)
    last_entities: dict[str, Any] = field(default_factory=dict)
    raw_turns: list[str] = field(default_factory=list)
    style: str = "customer_care"

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "preferred_language": (
                self.preferred_language.value if self.preferred_language else None
            ),
            "switch_count": self.switch_count,
            "low_confidence_streak": self.low_confidence_streak,
            "clarification_count": self.clarification_count,
            "failed_recognition_count": self.failed_recognition_count,
            "intent_success_count": self.intent_success_count,
            "turn_count": self.turn_count,
            "sheng_turns": self.sheng_turns,
            "last_intents": list(self.last_intents[-8:]),
            "last_entities": dict(self.last_entities),
            "style": self.style,
            "code_switch_rate": (
                round(self.switch_count / max(self.turn_count, 1), 4)
            ),
        }


class KenyaSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, KenyaIntelligenceSession] = {}

    def get(self, session_id: str) -> KenyaIntelligenceSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = KenyaIntelligenceSession(session_id=session_id)
        return self._sessions[session_id]

    def apply_language(
        self, session: KenyaIntelligenceSession, guess: LanguageGuess
    ) -> None:
        session.turn_count += 1
        if guess.primary_language == KenyaLanguage.SHENG or guess.sheng_hits:
            session.sheng_turns += 1
        if guess.switched:
            session.switch_count += 1
            session.preferred_language = guess.primary_language
        elif session.preferred_language is None and guess.confidence >= 0.45:
            session.preferred_language = guess.primary_language
        session.last_primary = guess.primary_language

    async def persist_ephemeral(
        self, organization_id: int, session: KenyaIntelligenceSession
    ) -> None:
        """Write non-PII session counters to Redis for multi-worker coordination."""
        from api.services.voice_runtime_cache import cache_set

        snap = session.snapshot()
        snap.pop("last_entities", None)
        snap.pop("raw_turns", None)
        await cache_set(
            organization_id,
            "kenya_sess",
            session.session_id,
            snap,
            ttl_s=3600,
        )


_STORE: KenyaSessionStore | None = None


def get_kenya_session_store() -> KenyaSessionStore:
    global _STORE
    if _STORE is None:
        _STORE = KenyaSessionStore()
    return _STORE
