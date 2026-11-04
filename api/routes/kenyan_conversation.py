"""FastAPI routes for Kenyan conversational behavior configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.schemas.kenyan_conversation import (
    RecoveryPromptRequest,
    RecoveryPromptResponse,
    StyleTransformRequest,
    StyleTransformResponse,
    SystemPromptRequest,
    SystemPromptResponse,
)
from api.services.auth.depends import get_user
from api.services.kenyan_conversation.factory import create_kenyan_conversation_behavior
from api.services.kenyan_conversation.types import TurnContext

router = APIRouter(prefix="/kenyan-conversation", tags=["kenyan-conversation"])


@router.post("/system-prompt", response_model=SystemPromptResponse)
async def build_system_prompt(body: SystemPromptRequest, _user=Depends(get_user)):
    behavior = create_kenyan_conversation_behavior(
        enabled=True,
        domain=body.domain,
        language_mode=body.language_mode,
    )
    return SystemPromptResponse(
        prompt=behavior.system_prompt(custom_instructions=body.custom_instructions),
        enabled=behavior.enabled,
    )


@router.post("/transform", response_model=StyleTransformResponse)
async def transform_response(body: StyleTransformRequest, _user=Depends(get_user)):
    behavior = create_kenyan_conversation_behavior(enabled=True)
    ctx = behavior.begin_turn(was_interrupted=body.was_interrupted)
    normalized = behavior.transform_response(body.text, ctx)
    chunks = [
        {"text": c.text, "pause_after_ms": c.pause_after_ms}
        for c in behavior.tts_chunks(normalized, ctx)
    ]
    return StyleTransformResponse(normalized=normalized, tts_chunks=chunks)


@router.post("/recovery-prompt", response_model=RecoveryPromptResponse)
async def recovery_prompt(body: RecoveryPromptRequest, _user=Depends(get_user)):
    behavior = create_kenyan_conversation_behavior(
        enabled=True,
        language_mode=body.language_mode,
    )
    ctx = TurnContext(was_interrupted=True, partial_spoken=body.partial_spoken)
    return RecoveryPromptResponse(
        recovery_prefix=behavior.recovery.recovery_prefix(ctx),
        spoken_recovery=behavior.recovery.spoken_recovery(ctx),
    )
