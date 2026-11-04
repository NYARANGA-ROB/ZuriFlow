"""Rolling context summarizer for low-latency memory compression."""

from __future__ import annotations

from api.services.realtime_conversation_memory.config import RealtimeMemoryConfig
from api.services.realtime_conversation_memory.types import CallIntent, IntentState, TurnRecord


class ContextSummarizer:
    """Extractive summarizer — no LLM round-trip, suitable for realtime voice."""

    def __init__(self, config: RealtimeMemoryConfig) -> None:
        self._config = config

    def summarize(
        self,
        turns: list[TurnRecord],
        intent: IntentState,
        *,
        prior_summary: str = "",
        partial_assistant: str = "",
        interrupted: bool = False,
    ) -> str:
        if not turns and not prior_summary:
            return self._intent_line(intent)

        parts: list[str] = []
        if prior_summary:
            parts.append(prior_summary.rstrip("."))

        goal = self._caller_goal(turns, intent)
        if goal:
            parts.append(goal)

        last_exchange = self._last_exchange(turns)
        if last_exchange:
            parts.append(last_exchange)

        if interrupted and partial_assistant:
            parts.append(f"Bot was interrupted mid-reply: \"{self._clip(partial_assistant, 80)}\"")

        if intent.slots:
            slot_str = ", ".join(f"{k}={v}" for k, v in intent.slots.items())
            parts.append(f"Known slots: {slot_str}")

        summary = ". ".join(p for p in parts if p)
        return self._clip(summary, self._config.max_summary_chars)

    def should_compress(self, turns: list[TurnRecord], pause_s: float) -> bool:
        return len(turns) >= self._config.max_turns // 2 or pause_s >= self._config.pause_recovery_s

    def compress_turns(self, turns: list[TurnRecord], intent: IntentState) -> str:
        """Compress older turns into a single summary line."""
        if not turns:
            return ""
        user_goals = [t.user_text for t in turns if t.user_text]
        unique = []
        for g in user_goals:
            if g and (not unique or g != unique[-1]):
                unique.append(g)
        compressed = f"Earlier caller asked about: {'; '.join(self._clip(u, 60) for u in unique[-3:])}"
        base = self._intent_line(intent)
        return self._clip(f"{base}. {compressed}", self._config.max_summary_chars)

    def _caller_goal(self, turns: list[TurnRecord], intent: IntentState) -> str:
        if not turns:
            return self._intent_line(intent)
        latest = turns[-1]
        if intent.current == CallIntent.UNKNOWN:
            return f"Caller said: \"{self._clip(latest.user_text, 100)}\""
        return f"Caller intent ({intent.current.value}): \"{self._clip(latest.user_text, 100)}\""

    def _last_exchange(self, turns: list[TurnRecord]) -> str:
        if len(turns) < 2:
            last = turns[-1] if turns else None
            if last and last.assistant_text:
                return f"Last reply: \"{self._clip(last.assistant_text, 100)}\""
            return ""
        prev, last = turns[-2], turns[-1]
        if last.assistant_text:
            return f"Last exchange — caller: \"{self._clip(last.user_text, 60)}\"; agent: \"{self._clip(last.assistant_text, 80)}\""
        if prev.assistant_text:
            return f"Prior agent reply: \"{self._clip(prev.assistant_text, 80)}\""
        return ""

    def _intent_line(self, intent: IntentState) -> str:
        if intent.current == CallIntent.UNKNOWN:
            return "No clear caller intent yet"
        return f"Active intent: {intent.current.value} (confidence {intent.confidence:.2f})"

    @staticmethod
    def _clip(text: str, max_len: int) -> str:
        text = text.strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 3].rstrip() + "..."
