"""Admin-editable Kenyan phrase catalog. File dictionary is the default; DB overlays it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

from api.services.kenyan_normalize.config import DEFAULT_KENYAN_NORMALIZE_CONFIG


@dataclass(frozen=True)
class CatalogPhrase:
    phrase: str
    meaning: str
    language: str
    intent: str | None
    confidence: float
    context: str
    region: str
    version: str
    active: bool
    organization_id: int | None = None
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "phrase": self.phrase,
            "meaning": self.meaning,
            "language": self.language,
            "intent": self.intent,
            "confidence": self.confidence,
            "context": self.context,
            "region": self.region,
            "version": self.version,
            "active": self.active,
            "organization_id": self.organization_id,
        }


def _default_path() -> Path:
    return Path(DEFAULT_KENYAN_NORMALIZE_CONFIG.dictionary_path)


class KenyanPhraseCatalog:
    """Longest-match phrase table with region/context metadata."""

    def __init__(self, path: Path | None = None) -> None:
        self._lock = RLock()
        self._path = path or _default_path()
        self._file_phrases: list[CatalogPhrase] = []
        self._overlay: list[CatalogPhrase] = []
        self.reload_file()

    def reload_file(self) -> None:
        phrases: list[CatalogPhrase] = []
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            version = str(data.get("version", "1.0.0"))
            for item in data.get("phrases", []):
                phrases.append(
                    CatalogPhrase(
                        phrase=str(item.get("source", "")).strip().lower(),
                        meaning=str(item.get("target", "")).strip(),
                        language=_language_from_tags(item.get("tags") or []),
                        intent=item.get("intent"),
                        confidence=float(item.get("confidence", 0.85)),
                        context=str(item.get("context") or ",".join(item.get("tags") or [])),
                        region=str(item.get("region") or "national"),
                        version=str(item.get("version") or version),
                        active=bool(item.get("active", True)),
                    )
                )
        with self._lock:
            self._file_phrases = [p for p in phrases if p.phrase]

    def set_overlay(self, phrases: list[CatalogPhrase]) -> None:
        with self._lock:
            self._overlay = [p for p in phrases if p.active and p.phrase]

    def all_active(self, *, region: str | None = None) -> list[CatalogPhrase]:
        with self._lock:
            rows = list(self._overlay) + list(self._file_phrases)
        if region:
            rows = [p for p in rows if p.region in {region, "national"}]
        seen: set[str] = set()
        out: list[CatalogPhrase] = []
        for p in rows:
            if not p.active or p.phrase in seen:
                continue
            seen.add(p.phrase)
            out.append(p)
        out.sort(key=lambda p: len(p.phrase), reverse=True)
        return out

    def match(self, text: str, *, region: str | None = None) -> CatalogPhrase | None:
        lowered = text.strip().lower()
        for phrase in self.all_active(region=region):
            if phrase.phrase in lowered:
                return phrase
        return None


def _language_from_tags(tags: list[str]) -> str:
    lowered = {t.lower() for t in tags}
    if "sheng" in lowered:
        return "sheng"
    if "swahili" in lowered or "kiswahili" in lowered:
        return "sw"
    if "code_switch" in lowered:
        return "mixed"
    return "en"


_CATALOG: KenyanPhraseCatalog | None = None


def get_phrase_catalog() -> KenyanPhraseCatalog:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = KenyanPhraseCatalog()
    return _CATALOG
