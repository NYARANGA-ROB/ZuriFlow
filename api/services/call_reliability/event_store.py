"""Durable append-only event log to prevent data loss."""

from __future__ import annotations

import json
import time
import uuid
from collections import OrderedDict
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

from api.constants import REDIS_URL
from api.services.call_reliability.config import CallReliabilityConfig, DEFAULT_CALL_RELIABILITY_CONFIG
from api.services.call_reliability.types import ReliabilityEvent, ReliabilityEventType


class DurableEventStore:
    """Persist call events before side-effects for replay and audit."""

    _LOCAL_IDEMPOTENCY_CAP = 10_000

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        *,
        config: CallReliabilityConfig | None = None,
    ) -> None:
        self._redis = redis_client
        self._config = config or DEFAULT_CALL_RELIABILITY_CONFIG
        self._seen_local: OrderedDict[str, str] = OrderedDict()

    def _remember_idempotency(self, key: str, event_id: str) -> None:
        self._seen_local[key] = event_id
        self._seen_local.move_to_end(key)
        while len(self._seen_local) > self._LOCAL_IDEMPOTENCY_CAP:
            self._seen_local.popitem(last=False)

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"call_reliability:events:{session_id}"

    @staticmethod
    def _workflow_key(workflow_run_id: int) -> str:
        return f"call_reliability:events:run:{workflow_run_id}"

    @staticmethod
    def _idempotency_key(key: str) -> str:
        return f"call_reliability:idempotency:{key}"

    async def append(self, event: ReliabilityEvent) -> ReliabilityEvent:
        if event.timestamp <= 0:
            event.timestamp = time.time()
        if not event.event_id:
            event.event_id = str(uuid.uuid4())

        if event.idempotency_key:
            if event.idempotency_key in self._seen_local:
                event.event_id = self._seen_local[event.idempotency_key]
                return event
            try:
                redis = await self._get_redis()
                inserted = await redis.setnx(
                    self._idempotency_key(event.idempotency_key),
                    event.event_id,
                )
                if not inserted:
                    existing_id = await redis.get(
                        self._idempotency_key(event.idempotency_key)
                    )
                    if existing_id:
                        event.event_id = str(existing_id)
                    self._remember_idempotency(event.idempotency_key, event.event_id)
                    return event
                await redis.expire(
                    self._idempotency_key(event.idempotency_key),
                    self._config.event_ttl_s,
                )
            except Exception:
                logger.warning(
                    "call_reliability idempotency check failed key={}",
                    event.idempotency_key,
                    exc_info=True,
                )
            self._remember_idempotency(event.idempotency_key, event.event_id)

        raw = json.dumps(event.to_dict(), separators=(",", ":"))
        try:
            redis = await self._get_redis()
            pipe = redis.pipeline()
            if event.session_id:
                key = self._session_key(event.session_id)
                pipe.rpush(key, raw)
                pipe.ltrim(key, -self._config.max_events_per_session, -1)
                pipe.expire(key, self._config.event_ttl_s)
            if event.workflow_run_id:
                wkey = self._workflow_key(event.workflow_run_id)
                pipe.rpush(wkey, raw)
                pipe.ltrim(wkey, -self._config.max_events_per_session, -1)
                pipe.expire(wkey, self._config.event_ttl_s)
            await pipe.execute()
        except Exception:
            logger.warning(
                "call_reliability event append failed session={} run={}",
                event.session_id,
                event.workflow_run_id,
                exc_info=True,
            )
        return event

    async def append_simple(
        self,
        event_type: ReliabilityEventType,
        *,
        organization_id: int,
        session_id: str = "",
        workflow_run_id: int = 0,
        payload: dict[str, Any] | None = None,
        idempotency_key: str = "",
    ) -> ReliabilityEvent:
        return await self.append(
            ReliabilityEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                organization_id=organization_id,
                session_id=session_id,
                workflow_run_id=workflow_run_id,
                timestamp=time.time(),
                payload=dict(payload or {}),
                idempotency_key=idempotency_key,
            )
        )

    async def list_session_events(
        self,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[ReliabilityEvent]:
        try:
            redis = await self._get_redis()
            raw_items = await redis.lrange(
                self._session_key(session_id), -limit, -1
            )
        except Exception:
            return []
        events: list[ReliabilityEvent] = []
        for raw in raw_items:
            try:
                events.append(ReliabilityEvent.from_dict(json.loads(raw)))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return events

    async def list_workflow_events(
        self,
        workflow_run_id: int,
        *,
        limit: int = 100,
    ) -> list[ReliabilityEvent]:
        try:
            redis = await self._get_redis()
            raw_items = await redis.lrange(
                self._workflow_key(workflow_run_id), -limit, -1
            )
        except Exception:
            return []
        events: list[ReliabilityEvent] = []
        for raw in raw_items:
            try:
                events.append(ReliabilityEvent.from_dict(json.loads(raw)))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return events


_store: DurableEventStore | None = None


def get_durable_event_store() -> DurableEventStore:
    global _store
    if _store is None:
        _store = DurableEventStore()
    return _store
