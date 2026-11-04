"""Expandable slang and Swahili dictionary manager."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from api.services.kenyan_normalize.config import KenyanNormalizeConfig


@dataclass(frozen=True)
class PhraseEntry:
    source: str
    target: str
    tags: tuple[str, ...] = ()
    intent: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhraseEntry:
        return cls(
            source=data["source"].strip().lower(),
            target=data["target"].strip(),
            tags=tuple(data.get("tags", [])),
            intent=data.get("intent"),
        )


@dataclass(frozen=True)
class TokenEntry:
    source: str
    target: str
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, source: str, target: str, meta: Any = None) -> TokenEntry:
        tags: tuple[str, ...] = ()
        if isinstance(meta, dict):
            tags = tuple(meta.get("tags", []))
        return cls(source=source.strip().lower(), target=str(target).strip(), tags=tags)


@dataclass
class SlangDictionaryManager:
    """Load, query, and extend Sheng / Swahili / code-switch dictionaries."""

    config: KenyanNormalizeConfig
    _phrases: list[PhraseEntry] = field(default_factory=list)
    _tokens: dict[str, TokenEntry] = field(default_factory=dict)
    _phrase_index: list[tuple[str, PhraseEntry]] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _version: str = "0.0.0"

    def __post_init__(self) -> None:
        self.reload()

    @property
    def version(self) -> str:
        return self._version

    @property
    def phrase_count(self) -> int:
        return len(self._phrases)

    @property
    def token_count(self) -> int:
        return len(self._tokens)

    def reload(self) -> None:
        with self._lock:
            path = self.config.dictionary_path
            if not path.exists():
                logger.warning("Kenyan normalize dictionary not found: {}", path)
                self._phrases = []
                self._tokens = {}
                self._rebuild_phrase_index()
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            self._version = str(data.get("version", "1.0.0"))
            self._phrases = [PhraseEntry.from_dict(p) for p in data.get("phrases", [])]
            self._tokens = {}
            for key, value in data.get("tokens", {}).items():
                if isinstance(value, dict):
                    self._tokens[key.lower()] = TokenEntry.from_dict(key, value.get("target", ""), value)
                else:
                    self._tokens[key.lower()] = TokenEntry.from_dict(key, value)
            self._rebuild_phrase_index()
            logger.info(
                "Kenyan normalize dictionary loaded phrases={} tokens={} version={}",
                len(self._phrases),
                len(self._tokens),
                self._version,
            )

    def _rebuild_phrase_index(self) -> None:
        self._phrase_index = sorted(
            ((p.source, p) for p in self._phrases),
            key=lambda x: len(x[0]),
            reverse=True,
        )

    def lookup_phrase(self, text: str) -> PhraseEntry | None:
        lowered = text.strip().lower()
        for source, entry in self._phrase_index:
            if lowered == source:
                return entry
        return None

    def find_phrase_prefix(self, text: str) -> tuple[PhraseEntry, int] | None:
        """Longest phrase match at the start of ``text``."""
        lowered = text.strip().lower()
        for source, entry in self._phrase_index:
            if lowered.startswith(source):
                end = len(source)
                if end == len(lowered) or lowered[end : end + 1].isspace():
                    return entry, end
        return None

    def lookup_token(self, token: str) -> TokenEntry | None:
        return self._tokens.get(token.lower())

    def all_token_keys(self) -> list[str]:
        return list(self._tokens.keys())

    def all_token_entries(self) -> list[TokenEntry]:
        return list(self._tokens.values())

    def add_phrase(
        self,
        source: str,
        target: str,
        *,
        tags: list[str] | None = None,
        intent: str | None = None,
        persist: bool = True,
    ) -> PhraseEntry:
        entry = PhraseEntry(
            source=source.strip().lower(),
            target=target.strip(),
            tags=tuple(tags or []),
            intent=intent,
        )
        with self._lock:
            self._phrases = [p for p in self._phrases if p.source != entry.source]
            self._phrases.append(entry)
            self._rebuild_phrase_index()
            if persist:
                self._persist()
        return entry

    def add_token(
        self,
        source: str,
        target: str,
        *,
        tags: list[str] | None = None,
        persist: bool = True,
    ) -> TokenEntry:
        entry = TokenEntry.from_dict(source, target, {"tags": tags or []})
        with self._lock:
            self._tokens[entry.source] = entry
            if persist:
                self._persist()
        return entry

    def remove_token(self, source: str, *, persist: bool = True) -> bool:
        with self._lock:
            removed = self._tokens.pop(source.lower(), None) is not None
            if removed and persist:
                self._persist()
            return removed

    def remove_phrase(self, source: str, *, persist: bool = True) -> bool:
        key = source.strip().lower()
        with self._lock:
            before = len(self._phrases)
            self._phrases = [p for p in self._phrases if p.source != key]
            removed = len(self._phrases) < before
            if removed:
                self._rebuild_phrase_index()
                if persist:
                    self._persist()
            return removed

    def _persist(self) -> None:
        path = self.config.dictionary_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self._version,
            "phrases": [
                {
                    "source": p.source,
                    "target": p.target,
                    "tags": list(p.tags),
                    **({"intent": p.intent} if p.intent else {}),
                }
                for p in self._phrases
            ],
            "tokens": {k: v.target for k, v in sorted(self._tokens.items())},
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": self._version,
                "phrase_count": len(self._phrases),
                "token_count": len(self._tokens),
                "phrases": [
                    {
                        "source": p.source,
                        "target": p.target,
                        "tags": list(p.tags),
                        "intent": p.intent,
                    }
                    for p in self._phrases
                ],
                "tokens": {k: v.target for k, v in sorted(self._tokens.items())},
            }

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Split text preserving apostrophes in Sheng contractions."""
        cleaned = re.sub(r"[^\w\s'-]", " ", text.lower())
        return [t for t in cleaned.split() if t]
