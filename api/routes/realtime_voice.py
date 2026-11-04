"""FastAPI routes for realtime voice pipeline over WebSocket audio."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, WebSocket
from loguru import logger

from api.db.models import UserModel
from api.services.auth.depends import get_user_ws
from api.services.realtime_audio import RealtimeAudioWebSocketServer
from api.services.realtime_audio.connection_manager import get_connection_manager
from api.services.realtime_voice_pipeline.factory import (
    create_realtime_voice_orchestrator_from_env,
)
from api.services.realtime_voice_pipeline.session_registry import (
    get_voice_pipeline_registry,
)
from api.services.tenant import assert_workflow_run_belongs_to_tenant
from api.services.tenant.access_control import resolve_tenant_context
from api.services.tenant.types import TenantContext

router = APIRouter(prefix="/realtime-voice", tags=["realtime-voice"])

_registry = get_voice_pipeline_registry()
_manager = get_connection_manager()


def _register_session_cleanup() -> None:
    async def _on_removed(session_id: str) -> None:
        await _registry.stop(session_id)

    _manager.register_on_session_removed(_on_removed)


_register_session_cleanup()


def _make_on_session_ready(ctx: TenantContext):
    async def on_session_ready(session, *, resumed: bool = False) -> None:
        meta = session.metadata or {}
        system_prompt = meta.get(
            "system_prompt", "You are a helpful voice assistant."
        )
        workflow_run_id = int(meta.get("workflow_run_id", 0))
        organization_id = ctx.organization_id
        meta["organization_id"] = organization_id
        session.metadata = meta

        if workflow_run_id:
            await assert_workflow_run_belongs_to_tenant(ctx, workflow_run_id)

        if not resumed and not all(
            os.environ.get(k)
            for k in (
                "DEEPGRAM_API_KEY",
                "OPENAI_API_KEY",
                "ELEVENLABS_API_KEY",
                "ELEVENLABS_VOICE_ID",
            )
        ):
            raise RuntimeError(
                "Missing API keys for realtime voice pipeline "
                "(DEEPGRAM_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID)"
            )

        def _factory():
            return create_realtime_voice_orchestrator_from_env(
                session,
                system_prompt=system_prompt,
                workflow_run_id=workflow_run_id,
            )

        await _registry.ensure_running(
            session.session_id,
            _factory,
            resumed=resumed,
        )

        if resumed:
            try:
                from api.constants import CALL_RELIABILITY_ENABLED
                if CALL_RELIABILITY_ENABLED:
                    from api.services.call_reliability.websocket_recovery import (
                        get_websocket_session_recovery,
                    )

                    await get_websocket_session_recovery().on_reconnected(
                        session_id=session.session_id,
                        organization_id=organization_id,
                        workflow_run_id=workflow_run_id,
                    )
            except Exception:
                pass

    return on_session_ready


@router.websocket("/ws")
async def realtime_voice_websocket(
    websocket: WebSocket,
    user: UserModel = Depends(get_user_ws),
):
    """Bidirectional PCM voice pipeline: STT → LLM → TTS.

    Uses the same audio protocol as ``/realtime-audio/ws``. After ``hello``,
    the server attaches the streaming voice pipeline to the session.

    API keys are read from environment variables:
      ``DEEPGRAM_API_KEY``, ``OPENAI_API_KEY``, ``ELEVENLABS_API_KEY``,
      ``ELEVENLABS_VOICE_ID``.

    Optional hello metadata::

        {"type":"hello","sample_rate":16000,"metadata":{"system_prompt":"..."}}
    """
    ctx = await resolve_tenant_context(user)
    from api.services.voice_runtime_cache import allow_ws_connect

    if not await allow_ws_connect(ctx.organization_id):
        await websocket.close(code=1008, reason="rate_limited")
        return
    server = RealtimeAudioWebSocketServer(
        websocket,
        organization_id=ctx.organization_id,
        on_session_ready=_make_on_session_ready(ctx),
    )
    session_id: str | None = None
    try:
        await server.run()
    finally:
        if server.session is not None:
            session_id = server.session.session_id
        if session_id and not _manager.session_in_grace(session_id):
            await _registry.stop(session_id)
        elif session_id:
            logger.debug(
                "voice pipeline kept alive for reconnect session_id={}",
                session_id[:8],
            )
