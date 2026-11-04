"""Conversation state manager with bounded memory."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from api.services.streaming_llm.config import StreamingLLMConfig, DEFAULT_STREAMING_LLM_CONFIG
from api.services.streaming_llm.types import ConversationMessage


@dataclass
class ConversationStateManager:
    """Thread-safe async conversation memory for streaming generations."""

    config: StreamingLLMConfig = DEFAULT_STREAMING_LLM_CONFIG
    system_prompt: str = ""
    _messages: list[ConversationMessage] = field(default_factory=list)

    def set_system_prompt(self, prompt: str) -> None:
        self.system_prompt = prompt.strip()

    def append(self, role: str, content: str, *, message_id: str | None = None) -> ConversationMessage:
        msg = ConversationMessage(
            role=role,
            content=content.strip(),
            message_id=message_id or uuid.uuid4().hex,
        )
        if not msg.content and role != "system":
            return msg
        self._messages.append(msg)
        self._trim()
        return msg

    def append_user(self, content: str) -> ConversationMessage:
        return self.append("user", content)

    def append_assistant(self, content: str) -> ConversationMessage:
        return self.append("assistant", content)

    def messages(self) -> list[ConversationMessage]:
        return list(self._messages)

    def export_openai_items(self) -> list[dict]:
        """Export messages for OpenAI Realtime conversation.item.create."""
        items = []
        for msg in self._messages:
            if msg.role not in {"user", "assistant"}:
                continue
            content_type = "input_text" if msg.role == "user" else "output_text"
            items.append(
                {
                    "type": "message",
                    "role": msg.role,
                    "content": [{"type": content_type, "text": msg.content}],
                }
            )
        return items

    def last_user_message(self) -> ConversationMessage | None:
        for msg in reversed(self._messages):
            if msg.role == "user":
                return msg
        return None

    def clear(self) -> None:
        self._messages.clear()

    def _trim(self) -> None:
        while len(self._messages) > self.config.max_messages:
            self._messages.pop(0)
        total = sum(len(m.content) for m in self._messages)
        while total > self.config.max_context_chars and self._messages:
            removed = self._messages.pop(0)
            total -= len(removed.content)
