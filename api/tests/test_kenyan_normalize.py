"""Unit tests for Kenyan language normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.services.kenyan_normalize.config import KenyanNormalizeConfig
from api.services.kenyan_normalize.dictionary.manager import SlangDictionaryManager
from api.services.kenyan_normalize.embeddings import EmbeddingSimilarityMatcher
from api.services.kenyan_normalize.normalizer import KenyanLanguageNormalizer
from api.services.kenyan_normalize.semantic import SemanticCorrectionLayer
from api.services.kenyan_normalize.service import KenyanNormalizeService
from api.services.kenyan_normalize.types import TokenSource


@pytest.fixture
def service(tmp_path: Path) -> KenyanNormalizeService:
    dict_path = tmp_path / "dictionary.json"
    default = Path(__file__).resolve().parents[1] / "data" / "kenyan_normalize" / "dictionary.json"
    dict_path.write_text(default.read_text(encoding="utf-8"), encoding="utf-8")
    cfg = KenyanNormalizeConfig(enabled=True, dictionary_path=dict_path)
    return KenyanNormalizeService(cfg)


def test_sasa_boss(service: KenyanNormalizeService):
    result = service.normalize("sasa boss")
    assert result.normalized == "hello boss"
    assert result.intent == "greeting"
    assert result.mappings[0].source == TokenSource.PHRASE


def test_nataka_balance_yangu(service: KenyanNormalizeService):
    result = service.normalize("nataka balance yangu")
    assert result.normalized == "I want my balance"
    assert result.intent == "request_balance"


def test_code_switch_check_balance(service: KenyanNormalizeService):
    result = service.normalize("check balance yangu")
    assert result.normalized == "check my balance"
    assert result.intent == "request_balance"


def test_token_path_reorders_possessive(service: KenyanNormalizeService):
    result = service.normalize("nataka salio yangu")
    assert result.normalized == "I want my balance"


def test_unknown_token_passthrough(service: KenyanNormalizeService):
    result = service.normalize("xyzabc foobar")
    assert "xyzabc" in result.normalized


def test_dictionary_add_token(tmp_path: Path):
    dict_path = tmp_path / "dict.json"
    dict_path.write_text(
        json.dumps({"version": "1.0", "phrases": [], "tokens": {"poa": "okay"}}),
        encoding="utf-8",
    )
    cfg = KenyanNormalizeConfig(enabled=True, dictionary_path=dict_path)
    mgr = SlangDictionaryManager(cfg)
    mgr.add_token("fiti", "cool", persist=True)
    assert mgr.lookup_token("fiti") is not None
    reloaded = json.loads(dict_path.read_text(encoding="utf-8"))
    assert reloaded["tokens"]["fiti"] == "cool"


def test_semantic_possessive_reorder():
    layer = SemanticCorrectionLayer(KenyanNormalizeConfig())
    corrected, maps = layer.correct("I want balance my", intent="request_balance")
    assert corrected == "I want my balance"
    assert maps


def test_embedding_matcher_fuzzy_typo(tmp_path: Path):
    dict_path = tmp_path / "dict.json"
    dict_path.write_text(
        json.dumps({"version": "1.0", "phrases": [], "tokens": {"nataka": "I want"}}),
        encoding="utf-8",
    )
    cfg = KenyanNormalizeConfig(enabled=True, dictionary_path=dict_path, similarity_threshold=0.6)
    mgr = SlangDictionaryManager(cfg)
    matcher = EmbeddingSimilarityMatcher(cfg, mgr)
    match = matcher.match_token("natak")  # typo of nataka
    assert match is not None
    assert match.target == "I want"
    assert match.score >= 0.6


def test_batch_normalize(service: KenyanNormalizeService):
    results = service.normalize_batch(["sasa boss", "asante sana"])
    assert results[0].normalized == "hello boss"
    assert results[1].normalized == "thank you very much"


def test_preserve_greeting_tone(service: KenyanNormalizeService):
    result = service.normalize("habari yako")
    assert result.normalized == "how are you"
    assert result.intent == "greeting"


def test_normalizer_exact_phrase_priority(tmp_path: Path):
    dict_path = tmp_path / "dict.json"
    dict_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "phrases": [{"source": "poa sana", "target": "I am very fine", "intent": "acknowledgment"}],
                "tokens": {"poa": "okay", "sana": "very much"},
            }
        ),
        encoding="utf-8",
    )
    cfg = KenyanNormalizeConfig(enabled=True, dictionary_path=dict_path)
    mgr = SlangDictionaryManager(cfg)
    matcher = EmbeddingSimilarityMatcher(cfg, mgr)
    semantic = SemanticCorrectionLayer(cfg)
    normalizer = KenyanLanguageNormalizer(cfg, mgr, matcher, semantic)
    result = normalizer.normalize("poa sana")
    assert result.normalized == "I am very fine"
    assert result.mappings[0].source == TokenSource.PHRASE
