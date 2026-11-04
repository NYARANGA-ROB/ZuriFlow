"""FastAPI routes for the realtime audio WebSocket server."""

from fastapi import APIRouter, Depends, WebSocket

from api.db.models import UserModel
from api.services.auth.depends import get_user_ws
from api.services.realtime_audio import RealtimeAudioWebSocketServer
from api.services.tenant.access_control import resolve_tenant_context

router = APIRouter(prefix="/realtime-audio", tags=["realtime-audio"])


@router.websocket("/ws")
async def realtime_audio_websocket(
    websocket: WebSocket,
    user: UserModel = Depends(get_user_ws),
):
    """Bidirectional PCM audio stream.

    Protocol:
      1. Client sends JSON ``hello`` or ``reconnect``.
      2. Server replies ``hello_ack`` with ``session_id`` + ``reconnect_token``.
      3. Client streams binary audio chunks; server streams binary responses.
      4. JSON ``ping``/``pong`` for heartbeat; ``disconnect`` for graceful close.

    Example hello::

        {"type":"hello","sample_rate":16000,"channels":1,"client_id":"my-app"}
    """
    ctx = await resolve_tenant_context(user)
    server = RealtimeAudioWebSocketServer(
        websocket, organization_id=ctx.organization_id
    )
    await server.run()
