"""Kenyan language normalization service."""

from __future__ import annotations

from api.services.kenyan_normalize.config import DEFAULT_KENYAN_NORMALIZE_CONFIG, KenyanNormalizeConfig
from api.services.kenyan_normalize.dictionary.manager import PhraseEntry, SlangDictionaryManager, TokenEntry
from api.services.kenyan_normalize.embeddings import EmbeddingSimilarityMatcher
from api.services.kenyan_normalize.normalizer import KenyanLanguageNormalizer
from api.services.kenyan_normalize.semantic import SemanticCorrectionLayer
from api.services.kenyan_normalize.types import NormalizeResult


class KenyanNormalizeService:
    """High-level API for normalizing Kenyan mixed-language utterances."""

    def __init__(self, config: KenyanNormalizeConfig = DEFAULT_KENYAN_NORMALIZE_CONFIG) -> None:
        self._config = config
        self._dictionary = SlangDictionaryManager(config)
        self._matcher = EmbeddingSimilarityMatcher(config, self._dictionary)
        self._semantic = SemanticCorrectionLayer(config)
        self._normalizer = KenyanLanguageNormalizer(
            config, self._dictionary, self._matcher, self._semantic
        )

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def dictionary(self) -> SlangDictionaryManager:
        return self._dictionary

    def normalize(self, text: str) -> NormalizeResult:
        if not self._config.enabled:
            return NormalizeResult(original=text, normalized=text)
        return self._normalizer.normalize(text)

    def normalize_batch(self, texts: list[str]) -> list[NormalizeResult]:
        return [self.normalize(t) for t in texts]

    def add_phrase(
        self,
        source: str,
        target: str,
        *,
        tags: list[str] | None = None,
        intent: str | None = None,
    ) -> PhraseEntry:
        entry = self._dictionary.add_phrase(source, target, tags=tags, intent=intent)
        self._matcher.refresh()
        return entry

    def add_token(self, source: str, target: str, *, tags: list[str] | None = None) -> TokenEntry:
        entry = self._dictionary.add_token(source, target, tags=tags)
        self._matcher.refresh()
        return entry

    def remove_token(self, source: str) -> bool:
        removed = self._dictionary.remove_token(source)
        if removed:
            self._matcher.refresh()
        return removed

    def remove_phrase(self, source: str) -> bool:
        removed = self._dictionary.remove_phrase(source)
        if removed:
            self._matcher.refresh()
        return removed

    def reload_dictionary(self) -> None:
        self._dictionary.reload()
        self._matcher.refresh()

    def similarity_lookup(self, token: str, top_k: int = 3):
        return self._matcher.top_k(token, top_k)


_service: KenyanNormalizeService | None = None


def get_kenyan_normalize_service() -> KenyanNormalizeService:
    global _service
    if _service is None:
        _service = KenyanNormalizeService()
    return _service
