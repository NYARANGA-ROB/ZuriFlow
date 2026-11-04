"""First-class Kenya market HTTP API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.db import db_client
from api.schemas.kenya import (
    KenyaConfirmKesRequest,
    KenyaCurrencyRequest,
    KenyaLocalizeRequest,
    KenyaPhoneRequest,
    KenyaPhraseCreate,
    KenyaPhraseUpdate,
)
from api.services.auth.depends import get_user
from api.services.kenya.analytics import get_kenya_analytics
from api.services.kenya.catalog import CatalogPhrase, get_phrase_catalog
from api.services.kenya.context import build_kenya_context
from api.services.kenya.currency import confirm_kes, parse_kes
from api.services.kenya.phone import normalize_kenyan_phone
from api.services.kenya.pipeline import process_kenya_turn
from api.services.kenya.styles import list_styles

router = APIRouter(prefix="/kenya", tags=["kenya"])


@router.get("/context")
async def get_kenya_context(user=Depends(get_user)) -> dict:
    _ = user
    return build_kenya_context().to_dict()


@router.get("/styles")
async def kenya_styles(user=Depends(get_user)) -> dict:
    _ = user
    return {"styles": list_styles()}


@router.post("/phone/normalize")
async def normalize_phone(body: KenyaPhoneRequest, user=Depends(get_user)) -> dict:
    _ = user
    return normalize_kenyan_phone(body.phone).to_dict()


@router.post("/currency/parse")
async def parse_currency(body: KenyaCurrencyRequest, user=Depends(get_user)) -> dict:
    _ = user
    return parse_kes(body.text).to_dict()


@router.post("/currency/confirm")
async def confirm_currency(body: KenyaConfirmKesRequest, user=Depends(get_user)) -> dict:
    _ = user
    parsed = parse_kes(body.text)
    return {
        **parsed.to_dict(),
        "confirmed": confirm_kes(parsed, body.confirmed_amount),
    }


@router.post("/localize")
async def localize_turn(body: KenyaLocalizeRequest, user=Depends(get_user)) -> dict:
    org_id = getattr(user, "selected_organization_id", None)
    return process_kenya_turn(
        body.transcript,
        session_id=body.session_id,
        organization_id=org_id,
        style=body.style,
        region=body.region,
    ).to_dict()


@router.get("/analytics")
async def kenya_analytics(user=Depends(get_user)) -> dict:
    org_id = getattr(user, "selected_organization_id", None)
    return get_kenya_analytics().snapshot(org_id)


@router.get("/phrases")
async def list_phrases(user=Depends(get_user)) -> dict:
    org_id = user.selected_organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")
    rows = await db_client.list_kenyan_phrases(organization_id=org_id)
    file_phrases = [p.to_dict() for p in get_phrase_catalog().all_active()]
    return {
        "file_phrases": file_phrases,
        "admin_phrases": [_phrase_row(r) for r in rows],
    }


@router.post("/phrases")
async def create_phrase(body: KenyaPhraseCreate, user=Depends(get_user)) -> dict:
    org_id = user.selected_organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")
    if body.global_phrase and not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Only superadmins can add global phrases")
    row = await db_client.create_kenyan_phrase(
        organization_id=None if body.global_phrase else org_id,
        phrase=body.phrase,
        meaning=body.meaning,
        language=body.language,
        intent=body.intent,
        confidence=body.confidence,
        context=body.context,
        region=body.region,
        version=body.version,
        is_active=body.is_active,
    )
    await _refresh_catalog(org_id)
    return _phrase_row(row)


@router.patch("/phrases/{phrase_id}")
async def update_phrase(
    phrase_id: int, body: KenyaPhraseUpdate, user=Depends(get_user)
) -> dict:
    org_id = user.selected_organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")
    row = await db_client.update_kenyan_phrase(
        phrase_id,
        organization_id=org_id,
        allow_global=bool(getattr(user, "is_superuser", False)),
        fields=body.model_dump(exclude_unset=True),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Phrase not found")
    await _refresh_catalog(org_id)
    return _phrase_row(row)


def _phrase_row(row) -> dict:
    return {
        "id": row.id,
        "phrase": row.phrase,
        "meaning": row.meaning,
        "language": row.language,
        "intent": row.intent,
        "confidence": row.confidence,
        "context": row.context,
        "region": row.region,
        "version": row.version,
        "active": row.is_active,
        "organization_id": row.organization_id,
    }


async def _refresh_catalog(organization_id: int) -> None:
    rows = await db_client.list_kenyan_phrases(
        organization_id=organization_id, active_only=True
    )
    get_phrase_catalog().set_overlay(
        [
            CatalogPhrase(
                phrase=r.phrase,
                meaning=r.meaning,
                language=r.language,
                intent=r.intent,
                confidence=float(r.confidence or 0.85),
                context=r.context or "",
                region=r.region or "national",
                version=r.version or "1",
                active=bool(r.is_active),
                organization_id=r.organization_id,
                id=r.id,
            )
            for r in rows
        ]
    )
