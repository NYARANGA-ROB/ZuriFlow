"""Pydantic schemas for Kenyan language normalization API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TokenMappingSchema(BaseModel):
    original: str
    normalized: str
    source: str
    confidence: float


class SimilarityMatchSchema(BaseModel):
    query: str
    matched_key: str
    target: str
    score: float


class NormalizeResultSchema(BaseModel):
    original: str
    normalized: str
    intent: str | None = None
    mappings: list[TokenMappingSchema] = Field(default_factory=list)
    similarity_matches: list[SimilarityMatchSchema] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class NormalizeBatchRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=50)


class NormalizeBatchResponse(BaseModel):
    results: list[NormalizeResultSchema]
    enabled: bool


class NormalizeResponse(BaseModel):
    result: NormalizeResultSchema
    enabled: bool


class DictionaryPhraseSchema(BaseModel):
    source: str
    target: str
    tags: list[str] = Field(default_factory=list)
    intent: str | None = None


class DictionaryTokenSchema(BaseModel):
    source: str
    target: str
    tags: list[str] = Field(default_factory=list)


class AddPhraseRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=200)
    target: str = Field(..., min_length=1, max_length=500)
    tags: list[str] = Field(default_factory=list)
    intent: str | None = None
    persist: bool = True


class AddTokenRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=100)
    target: str = Field(..., min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list)
    persist: bool = True


class DictionaryStatusSchema(BaseModel):
    enabled: bool
    version: str
    phrase_count: int
    token_count: int
    dictionary_path: str


class DictionarySnapshotSchema(BaseModel):
    version: str
    phrase_count: int
    token_count: int
    phrases: list[DictionaryPhraseSchema]
    tokens: dict[str, str]


class SimilarityRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=100)
    top_k: int = Field(default=3, ge=1, le=10)


class SimilarityResponse(BaseModel):
    matches: list[SimilarityMatchSchema]
