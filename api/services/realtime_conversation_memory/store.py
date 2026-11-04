"""In-memory store for per-call conversation state."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import RLock

from api.services.realtime_conversation_memory.config import RealtimeMemoryConfig
from api.services.realtime_conversation_memory.types import IntentState, TurnRecord, TurnStatus


@dataclass
class SessionMemory:
    session_id: str
    turns: deque[TurnRecord] = field(default_factory=deque)
    intent: IntentState = field(default_factory=IntentState)
    summary: str = ""
    interrupted: bool = False
    partial_assistant: str = ""
    open_turn: TurnRecord | None = None
    last_activity: float = field(default_factory=time.monotonic)
    pause_started: float | None = None
    turn_counter: int = 0

    def touch_activity(self) -> None:
        self.last_activity = time.monotonic()
        self.pause_started = None


class MemoryStore:
    """Process-local low-latency memory store keyed by call session_id."""

    def __init__(self, config: RealtimeMemoryConfig) -> None:
        self._config = config
        self._sessions: dict[str, SessionMemory] = {}
        self._lock = RLock()

    def get_or_create(self, session_id: str) -> SessionMemory:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is None:
                mem = SessionMemory(session_id=session_id)
                self._sessions[session_id] = mem
            return mem

    def get(self, session_id: str) -> SessionMemory | None:
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> SessionMemory | None:
        with self._lock:
            return self._sessions.pop(session_id, None)

    def touch(self, session_id: str) -> None:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is not None:
                mem.last_activity = time.monotonic()
                mem.pause_started = None

    def begin_turn(self, session_id: str, user_text: str) -> TurnRecord:
        with self._lock:
            mem = self.get_or_create(session_id)
            mem.turn_counter += 1
            mem.touch_activity()
            turn = TurnRecord(
                turn_id=mem.turn_counter,
                user_text=user_text.strip(),
                timestamp=time.monotonic(),
            )
            mem.open_turn = turn
            return turn

    def complete_turn(
        self,
        session_id: str,
        assistant_text: str,
        *,
        interrupted: bool = False,
    ) -> TurnRecord | None:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is None or mem.open_turn is None:
                return None
            turn = mem.open_turn
            turn.assistant_text = assistant_text.strip()
            turn.interrupted = interrupted
            turn.status = TurnStatus.INTERRUPTED if interrupted else TurnStatus.COMPLETE
            mem.turns.append(turn)
            while len(mem.turns) > self._config.max_turns:
                mem.turns.popleft()
            mem.open_turn = None
            mem.interrupted = interrupted
            mem.partial_assistant = assistant_text if interrupted else ""
            mem.touch_activity()
            return turn

    def mark_interrupted(self, session_id: str, partial_assistant: str = "") -> None:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is None:
                return
            mem.interrupted = True
            mem.partial_assistant = partial_assistant
            if mem.open_turn is not None:
                mem.open_turn.interrupted = True
                mem.open_turn.status = TurnStatus.INTERRUPTED
                mem.open_turn.assistant_text = partial_assistant

    def clear_interrupt(self, session_id: str) -> None:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is None:
                return
            mem.interrupted = False
            mem.partial_assistant = ""

    def set_summary(self, session_id: str, summary: str) -> None:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is not None:
                mem.summary = summary[: self._config.max_summary_chars]

    def set_intent(self, session_id: str, intent_state: IntentState) -> None:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is not None:
                mem.intent = intent_state

    def pause_elapsed_s(self, session_id: str) -> float:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is None:
                return 0.0
            now = time.monotonic()
            if mem.pause_started is None:
                elapsed = now - mem.last_activity
                if elapsed >= self._config.pause_recovery_s:
                    mem.pause_started = mem.last_activity
                    return elapsed
                return 0.0
            return now - mem.pause_started

    def recent_turns(self, session_id: str, limit: int = 4) -> list[TurnRecord]:
        with self._lock:
            mem = self._sessions.get(session_id)
            if mem is None:
                return []
            return list(mem.turns)[-limit:]
