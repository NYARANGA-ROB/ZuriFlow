"""FastAPI routes for Kenyan English accent detection."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

from api.schemas.kenyan_accent import (
    AccentPredictionSchema,
    AccentScoresSchema,
    AccentStatusResponse,
    ClassifyPCMRequest,
    ClassifyPCMResponse,
    ConfidenceFactorsSchema,
    StreamChunkRequest,
    StreamChunkResponse,
    StreamResultResponse,
    StreamSessionResponse,
)
from api.services.auth.depends import get_user, get_user_ws
from api.services.kenyan_accent.service import get_kenyan_accent_service
from api.services.kenyan_accent.types import AccentPrediction
from api.services.tenant import assert_session_belongs_to_tenant, register_session_organization
from api.services.tenant.access_control import resolve_tenant_context
from api.services.tenant.route_helpers import TenantContextDep

router = APIRouter(prefix="/kenyan-accent", tags=["kenyan-accent"])


def _to_schema(prediction: AccentPrediction) -> AccentPredictionSchema:
    return AccentPredictionSchema(
        label=prediction.label.value,
        probability=prediction.probability,
        confidence=prediction.confidence,
        scores=AccentScoresSchema(
            generic_english=prediction.scores.generic_english,
            kenyan_english=prediction.scores.kenyan_english,
        ),
        factors=ConfidenceFactorsSchema(**prediction.factors.to_dict()),
        is_stable=prediction.is_stable,
        session_id=prediction.session_id,
    )


@router.get("/status", response_model=AccentStatusResponse)
async def accent_status(_user=Depends(get_user)):
    service = get_kenyan_accent_service()
    cfg = service._config  # noqa: SLF001 — status endpoint
    return AccentStatusResponse(
        enabled=service.enabled,
        model_loaded=service._classifier.weights_loaded,
        pyannote_available=service._segmenter.pyannote_used,
        config={
            "target_sample_rate": cfg.target_sample_rate,
            "window_s": cfg.window_s,
            "hop_s": cfg.hop_s,
            "min_confidence": cfg.min_confidence,
        },
    )


@router.post("/classify", response_model=ClassifyPCMResponse)
async def classify_pcm(body: ClassifyPCMRequest, _user=Depends(get_user)):
    service = get_kenyan_accent_service()
    if not service.enabled:
        return ClassifyPCMResponse(prediction=None, enabled=False)

    try:
        pcm = base64.b64decode(body.pcm_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid base64 PCM: {e}") from e

    prediction = await service.classify_pcm(
        pcm, sample_rate=body.sample_rate, session_id=body.session_id
    )
    return ClassifyPCMResponse(
        prediction=_to_schema(prediction) if prediction else None,
        enabled=True,
    )


@router.post("/stream/start", response_model=StreamSessionResponse)
async def start_stream(*, sample_rate: int = 16000, ctx: TenantContextDep):
    service = get_kenyan_accent_service()
    if not service.enabled:
        raise HTTPException(status_code=503, detail="Kenyan accent detection is disabled")
    session_id = await service.start_session(sample_rate=sample_rate)
    await register_session_organization(session_id, ctx.organization_id)
    return StreamSessionResponse(session_id=session_id, sample_rate=sample_rate)


@router.post("/stream/{session_id}/chunk", response_model=StreamChunkResponse)
async def stream_chunk(
    session_id: str, body: StreamChunkRequest, ctx: TenantContextDep
):
    service = get_kenyan_accent_service()
    if not service.enabled:
        raise HTTPException(status_code=503, detail="Kenyan accent detection is disabled")
    await assert_session_belongs_to_tenant(ctx, session_id)

    try:
        pcm = base64.b64decode(body.pcm_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid base64 PCM: {e}") from e

    prediction = await service.push_chunk(
        session_id, pcm, sample_rate=body.sample_rate
    )
    return StreamChunkResponse(
        session_id=session_id,
        prediction=_to_schema(prediction) if prediction else None,
    )


@router.get("/stream/{session_id}/result", response_model=StreamResultResponse)
async def stream_result(session_id: str, ctx: TenantContextDep):
    await assert_session_belongs_to_tenant(ctx, session_id)
    service = get_kenyan_accent_service()
    prediction = await service.get_session_result(session_id)
    if prediction is None and not await service.has_session(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return StreamResultResponse(
        session_id=session_id,
        prediction=_to_schema(prediction) if prediction else None,
    )


@router.delete("/stream/{session_id}", response_model=StreamResultResponse)
async def end_stream(session_id: str, ctx: TenantContextDep):
    await assert_session_belongs_to_tenant(ctx, session_id)
    service = get_kenyan_accent_service()
    prediction = await service.end_session(session_id)
    return StreamResultResponse(
        session_id=session_id,
        prediction=_to_schema(prediction) if prediction else None,
    )


@router.websocket("/ws")
async def accent_websocket(
    websocket: WebSocket,
    user=Depends(get_user_ws),
):
    """Stream PCM chunks as JSON messages for realtime accent detection.

    Message format::

        {"pcm_base64": "...", "sample_rate": 16000}

    Server replies with prediction JSON or ``{"type": "noop"}`` when buffering.
    """
    ctx = await resolve_tenant_context(user)
    await websocket.accept()
    service = get_kenyan_accent_service()
    if not service.enabled:
        await websocket.send_json({"error": "disabled"})
        await websocket.close(code=1013)
        return

    session_id = await service.start_session()
    await register_session_organization(session_id, ctx.organization_id)
    try:
        await websocket.send_json({"type": "ready", "session_id": session_id})
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "end":
                final = await service.end_session(session_id)
                await websocket.send_json(
                    {
                        "type": "final",
                        "prediction": final.to_dict() if final else None,
                    }
                )
                break

            pcm_b64 = msg.get("pcm_base64", "")
            sample_rate = int(msg.get("sample_rate", 16000))
            pcm = base64.b64decode(pcm_b64)
            prediction = await service.push_chunk(session_id, pcm, sample_rate=sample_rate)
            if prediction is not None:
                await websocket.send_json(
                    {"type": "prediction", "prediction": prediction.to_dict()}
                )
            else:
                await websocket.send_json({"type": "noop"})
    except WebSocketDisconnect:
        logger.debug("Kenyan accent WS disconnected session_id={}", session_id[:8])
    finally:
        await service.end_session(session_id)
