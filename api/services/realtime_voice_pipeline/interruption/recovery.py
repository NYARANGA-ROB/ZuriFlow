"""Conversation state recovery after caller interruptions."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.services.voice_pipeline.types import LLMMessage


@dataclass
class ConversationRecoveryManager:
    """Keeps conversation history coherent when the bot is interrupted mid-response."""

    _messages: list[LLMMessage] = field(default_factory=list)
    _interrupted: bool = False
    _partial_assistant: str = ""
    _pending_user_after_interrupt: bool = False

    @property
    def messages(self) -> list[LLMMessage]:
        return list(self._messages)

    def append_user(self, text: str) -> None:
        self._messages.append(LLMMessage(role="user", content=text.strip()))
        if self._interrupted:
            self._pending_user_after_interrupt = True

    def begin_assistant_turn(self) -> None:
        self._partial_assistant = ""
        self._interrupted = False

    def append_assistant_delta(self, delta: str) -> None:
        self._partial_assistant += delta

    def on_interruption(self, *, partial_assistant: str | None = None) -> None:
        """Record interruption; discard incomplete assistant output."""
        self._interrupted = True
        if partial_assistant is not None:
            self._partial_assistant = partial_assistant
        # Remove a trailing partial assistant message if one was committed early.
        if self._messages and self._messages[-1].role == "assistant":
            if self._partial_assistant and self._messages[-1].content.startswith(
                self._partial_assistant[:20]
            ):
                self._messages.pop()

    def complete_assistant_turn(self, text: str) -> bool:
        """Append assistant reply when the turn finished without interruption."""
        if self._interrupted:
            return False
        cleaned = text.strip()
        if cleaned:
            self._messages.append(LLMMessage(role="assistant", content=cleaned))
        self._partial_assistant = ""
        return True

    def resume_after_interrupt(self) -> None:
        """STT is listening again; ready for the caller's next utterance."""
        self._interrupted = False
        self._partial_assistant = ""
        self._pending_user_after_interrupt = False

    def messages_for_generation(self) -> list[LLMMessage]:
        """Messages passed to the LLM for the next turn."""
        return list(self._messages)

    def was_interrupted(self) -> bool:
        return self._interrupted

    def partial_assistant_text(self) -> str:
        return self._partial_assistant
