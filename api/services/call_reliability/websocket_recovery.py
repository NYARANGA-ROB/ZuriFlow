"""WebSocket session checkpointing for reconnect recovery."""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

from api.constants import REDIS_URL
from api.services.call_reliability.config import CallReliabilityConfig, DEFAULT_CALL_RELIABILITY_CONFIG
from api.services.call_reliability.event_store import get_durable_event_store
from api.services.call_reliability.types import ReliabilityEventType


class WebSocketSessionRecovery:
    """Persist voice session state across WebSocket reconnects."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        *,
        config: CallReliabilityConfig | None = None,
    ) -> None:
        self._redis = redis_client
        self._config = config or DEFAULT_CALL_RELIABILITY_CONFIG

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _checkpoint_key(session_id: str) -> str:
        return f"call_reliability:ws_checkpoint:{session_id}"

    async def save_checkpoint(
        self,
        *,
        session_id: str,
        organization_id: int = 0,
        workflow_run_id: int = 0,
        state: dict[str, Any],
    ) -> None:
        payload = {
            "session_id": session_id,
            "organization_id": organization_id,
            "workflow_run_id": workflow_run_id,
            "updated_at": time.time(),
            "state": state,
        }
        try:
            redis = await self._get_redis()
            await redis.setex(
                self._checkpoint_key(session_id),
                self._config.ws_checkpoint_ttl_s,
                json.dumps(payload, separators=(",", ":")),
            )
        except Exception:
            pass

        store = get_durable_event_store()
        await store.append_simple(
            ReliabilityEventType.WEBSOCKET_DISCONNECTED,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            payload={"checkpoint": state},
            idempotency_key=f"ws_checkpoint:{session_id}:{int(time.time()) // 30}",
        )

    async def load_checkpoint(self, session_id: str) -> dict[str, Any] | None:
        try:
            redis = await self._get_redis()
            raw = await redis.get(self._checkpoint_key(session_id))
        except Exception:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return dict(data.get("state") or {})
        except json.JSONDecodeError:
            return None

    async def on_reconnected(
        self,
        *,
        session_id: str,
        organization_id: int = 0,
        workflow_run_id: int = 0,
    ) -> dict[str, Any] | None:
        state = await self.load_checkpoint(session_id)
        store = get_durable_event_store()
        await store.append_simple(
            ReliabilityEventType.WEBSOCKET_RECONNECTED,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            payload={"restored": state is not None},
        )
        return state


_ws_recovery: WebSocketSessionRecovery | None = None


def get_websocket_session_recovery() -> WebSocketSessionRecovery:
    global _ws_recovery
    if _ws_recovery is None:
        _ws_recovery = WebSocketSessionRecovery()
    return _ws_recovery
