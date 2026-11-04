"""Response style middleware — concise, natural Kenyan voice output."""

from __future__ import annotations

import re

from api.services.kenyan_conversation.config import KenyanConversationConfig

_ROBOTIC_PATTERNS = [
    r"^certainly[!.,]?\s*",
    r"^absolutely[!.,]?\s*",
    r"^of course[!.,]?\s*",
    r"^i(?:'d| would) be happy to (?:help|assist)[!.,]?\s*",
    r"^i understand that you\b",
    r"^thank you for (?:calling|reaching out|contacting)\b[^.]*[.]\s*",
    r"^as an ai(?: assistant)?[,]?\s*",
    r"^great question[!.,]?\s*",
    r"^i appreciate your (?:patience|question)[!.,]?\s*",
]

_ROBOTIC_RE = [re.compile(p, re.IGNORECASE) for p in _ROBOTIC_PATTERNS]


class ResponseStyleMiddleware:
    """Transform LLM tokens and final text for natural Kenyan phone speech."""

    def __init__(self, config: KenyanConversationConfig) -> None:
        self._config = config
        self._buffer = ""

    def reset(self) -> None:
        self._buffer = ""

    def transform_token(self, token: str) -> str:
        if not token:
            return token
        self._buffer += token
        return self._strip_robotic(token) if self._config.strip_robotic_phrases else token

    def transform_complete(self, text: str) -> str:
        cleaned = text.strip()
        if self._config.strip_robotic_phrases:
            cleaned = self._strip_robotic_full(cleaned)
        cleaned = self._enforce_concision(cleaned)
        cleaned = self._collapse_whitespace(cleaned)
        return cleaned

    def _strip_robotic(self, token: str) -> str:
        # Only strip at the very start of the turn buffer
        if len(self._buffer) > len(token) + 5:
            return token
        for pattern in _ROBOTIC_RE:
            match = pattern.match(self._buffer)
            if match:
                removed = match.group(0)
                self._buffer = self._buffer[len(removed) :]
                return self._buffer[: len(token)] if self._buffer else ""
        return token

    def _strip_robotic_full(self, text: str) -> str:
        result = text
        for pattern in _ROBOTIC_RE:
            result = pattern.sub("", result)
        return result.strip()

    def _enforce_concision(self, text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return text

        trimmed: list[str] = []
        for sentence in sentences[: self._config.max_sentences_per_turn]:
            words = sentence.split()
            if len(words) > self._config.max_words_per_sentence:
                chunk = " ".join(words[: self._config.max_words_per_sentence])
                if not chunk.endswith((".", "!", "?")):
                    chunk += "."
                trimmed.append(chunk)
            else:
                trimmed.append(sentence)

        return " ".join(trimmed)

    @staticmethod
    def _collapse_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()
