"""FastAPI routes for Kenyan language normalization."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.schemas.kenyan_normalize import (
    AddPhraseRequest,
    AddTokenRequest,
    DictionarySnapshotSchema,
    DictionaryStatusSchema,
    NormalizeBatchRequest,
    NormalizeBatchResponse,
    NormalizeRequest,
    NormalizeResponse,
    NormalizeResultSchema,
    SimilarityMatchSchema,
    SimilarityRequest,
    SimilarityResponse,
    TokenMappingSchema,
)
from api.services.auth.depends import get_user
from api.services.kenyan_normalize.service import get_kenyan_normalize_service
from api.services.kenyan_normalize.types import NormalizeResult

router = APIRouter(prefix="/kenyan-normalize", tags=["kenyan-normalize"])


def _result_schema(result: NormalizeResult) -> NormalizeResultSchema:
    data = result.to_dict()
    return NormalizeResultSchema(
        original=data["original"],
        normalized=data["normalized"],
        intent=data.get("intent"),
        mappings=[TokenMappingSchema(**m) for m in data.get("mappings", [])],
        similarity_matches=[
            SimilarityMatchSchema(**s) for s in data.get("similarity_matches", [])
        ],
        metadata=data.get("metadata", {}),
    )


@router.get("/status", response_model=DictionaryStatusSchema)
async def normalize_status(_user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    cfg = service._config  # noqa: SLF001
    return DictionaryStatusSchema(
        enabled=service.enabled,
        version=service.dictionary.version,
        phrase_count=service.dictionary.phrase_count,
        token_count=service.dictionary.token_count,
        dictionary_path=str(cfg.dictionary_path),
    )


@router.post("/normalize", response_model=NormalizeResponse)
async def normalize_text(body: NormalizeRequest, _user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    result = service.normalize(body.text)
    return NormalizeResponse(result=_result_schema(result), enabled=service.enabled)


@router.post("/normalize/batch", response_model=NormalizeBatchResponse)
async def normalize_batch(body: NormalizeBatchRequest, _user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    results = service.normalize_batch(body.texts)
    return NormalizeBatchResponse(
        results=[_result_schema(r) for r in results],
        enabled=service.enabled,
    )


@router.get("/dictionary", response_model=DictionarySnapshotSchema)
async def get_dictionary(_user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    snap = service.dictionary.export_snapshot()
    return DictionarySnapshotSchema(
        version=snap["version"],
        phrase_count=snap["phrase_count"],
        token_count=snap["token_count"],
        phrases=snap["phrases"],
        tokens=snap["tokens"],
    )


@router.post("/dictionary/reload")
async def reload_dictionary(_user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    service.reload_dictionary()
    return {"status": "reloaded", "version": service.dictionary.version}


@router.post("/dictionary/phrases")
async def add_phrase(body: AddPhraseRequest, _user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    entry = service.add_phrase(
        body.source,
        body.target,
        tags=body.tags,
        intent=body.intent,
    )
    return {"source": entry.source, "target": entry.target, "intent": entry.intent}


@router.post("/dictionary/tokens")
async def add_token(body: AddTokenRequest, _user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    entry = service.add_token(body.source, body.target, tags=body.tags)
    return {"source": entry.source, "target": entry.target}


@router.delete("/dictionary/tokens/{source}")
async def remove_token(source: str, _user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    if not service.remove_token(source):
        raise HTTPException(status_code=404, detail="token not found")
    return {"removed": source}


@router.delete("/dictionary/phrases/{source}")
async def remove_phrase(source: str, _user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    if not service.remove_phrase(source):
        raise HTTPException(status_code=404, detail="phrase not found")
    return {"removed": source}


@router.post("/similarity", response_model=SimilarityResponse)
async def similarity_lookup(body: SimilarityRequest, _user=Depends(get_user)):
    service = get_kenyan_normalize_service()
    matches = service.similarity_lookup(body.token, body.top_k)
    return SimilarityResponse(
        matches=[SimilarityMatchSchema(**m.__dict__) for m in matches]
    )
