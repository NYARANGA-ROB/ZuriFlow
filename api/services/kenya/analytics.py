"""In-memory Kenyan conversation analytics (hot path stays off the database)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class _OrgCounters:
    turns: int = 0
    sheng_turns: int = 0
    code_switches: int = 0
    failed_recognition: int = 0
    clarifications: int = 0
    escalations: int = 0
    intent_success: int = 0
    completed_by_language: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    language_turns: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    mix_turns: dict[str, int] = field(default_factory=lambda: defaultdict(int))


class KenyanConversationAnalytics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._orgs: dict[int, _OrgCounters] = defaultdict(_OrgCounters)

    def record(self, organization_id: int | None, payload: dict[str, Any]) -> None:
        org_id = organization_id or 0
        with self._lock:
            c = self._orgs[org_id]
            c.turns += 1
            lang = str(payload.get("primary_language") or "unknown")
            c.language_turns[lang] += 1
            mix = str(payload.get("mix") or "none")
            c.mix_turns[mix] += 1
            if payload.get("sheng"):
                c.sheng_turns += 1
            if payload.get("code_switched"):
                c.code_switches += 1
            if payload.get("failed_recognition"):
                c.failed_recognition += 1
            if payload.get("clarification"):
                c.clarifications += 1
            if payload.get("escalation"):
                c.escalations += 1
            if payload.get("intent_success"):
                c.intent_success += 1
            if payload.get("completed"):
                c.completed_by_language[lang] += 1

    def snapshot(self, organization_id: int | None = None) -> dict[str, Any]:
        org_id = organization_id or 0
        with self._lock:
            c = self._orgs[org_id]
            turns = max(c.turns, 1)
            return {
                "turns": c.turns,
                "language_distribution": dict(c.language_turns),
                "sheng_usage_rate": round(c.sheng_turns / turns, 4),
                "code_switching_rate": round(c.code_switches / turns, 4),
                "failed_recognition_rate": round(c.failed_recognition / turns, 4),
                "clarification_rate": round(c.clarifications / turns, 4),
                "escalation_rate": round(c.escalations / turns, 4),
                "successful_intent_rate": round(c.intent_success / turns, 4),
                "language_specific_completion": dict(c.completed_by_language),
                "mix_distribution": dict(c.mix_turns),
            }


_ANALYTICS: KenyanConversationAnalytics | None = None


def get_kenya_analytics() -> KenyanConversationAnalytics:
    global _ANALYTICS
    if _ANALYTICS is None:
        _ANALYTICS = KenyanConversationAnalytics()
    return _ANALYTICS
