"""Escalation queues with priority routing and operator claims."""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

from api.constants import REDIS_URL
from api.services.call_routing.config import CallRoutingOrgConfig
from api.services.call_routing.queue_service import CallRoutingQueueService
from api.services.call_routing.types import QueueEntry
from api.services.human_escalation.types import HandoffPackage, OperatorClaim


class EscalationQueueService:
    """Priority escalation queues with handoff packages and operator claims."""

    def __init__(
        self,
        *,
        queue_service: CallRoutingQueueService | None = None,
        redis_client: aioredis.Redis | None = None,
        handoff_ttl_s: int = 3600,
    ) -> None:
        self._queues = queue_service or CallRoutingQueueService()
        self._redis = redis_client
        self._handoff_ttl_s = handoff_ttl_s

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def _handoff_key(session_id: str) -> str:
        return f"human_escalation:handoff:{session_id}"

    @staticmethod
    def _claim_key(session_id: str) -> str:
        return f"human_escalation:claim:{session_id}"

    @staticmethod
    def _org_index_key(organization_id: int) -> str:
        return f"human_escalation:org:{organization_id}:sessions"

    async def store_handoff(self, handoff: HandoffPackage) -> None:
        redis = await self._get_redis()
        payload = json.dumps(handoff.to_dict())
        pipe = redis.pipeline()
        pipe.setex(self._handoff_key(handoff.session_id), self._handoff_ttl_s, payload)
        pipe.sadd(self._org_index_key(handoff.organization_id), handoff.session_id)
        pipe.expire(self._org_index_key(handoff.organization_id), self._handoff_ttl_s)
        await pipe.execute()

    async def get_handoff(self, session_id: str) -> HandoffPackage | None:
        redis = await self._get_redis()
        raw = await redis.get(self._handoff_key(session_id))
        if not raw:
            return None
        return HandoffPackage.from_dict(json.loads(raw))

    async def enqueue_with_handoff(
        self,
        handoff: HandoffPackage,
        *,
        org_config: CallRoutingOrgConfig,
    ) -> tuple[bool, int]:
        await self.store_handoff(handoff)
        priority = self._compute_priority(handoff)
        entry = QueueEntry(
            session_id=handoff.session_id,
            organization_id=handoff.organization_id,
            queue_name=handoff.queue_name or "human",
            priority=priority,
            intent=handoff.intent,
            language=handoff.language,
            enqueued_at=time.time(),
            workflow_run_id=handoff.workflow_run_id,
            phone_e164=handoff.phone_e164,
            metadata={
                "reason": handoff.reason,
                "risk_level": handoff.risk_level,
                "customer_name": handoff.customer_name,
                "summary_preview": handoff.summary[:200],
            },
        )
        return await self._queues.enqueue(entry, org_config=org_config)

    @staticmethod
    def _compute_priority(handoff: HandoffPackage) -> int:
        base = int(handoff.priority)
        risk_boost = {"critical": 40, "high": 25, "medium": 10, "low": 0}
        base += risk_boost.get(handoff.risk_level.lower(), 0)
        return min(100, max(1, base))

    async def claim_for_operator(
        self,
        organization_id: int,
        queue_name: str,
        *,
        operator_id: int,
    ) -> OperatorClaim | None:
        entry = await self._queues.dequeue_next(organization_id, queue_name)
        if entry is None:
            return None

        handoff = await self.get_handoff(entry.session_id)
        if handoff is None:
            handoff = HandoffPackage(
                session_id=entry.session_id,
                organization_id=entry.organization_id,
                workflow_run_id=entry.workflow_run_id,
                phone_e164=entry.phone_e164,
                intent=entry.intent,
                language=entry.language,
                queue_name=queue_name,
                reason=str(entry.metadata.get("reason", "")),
            )

        claim = OperatorClaim(
            session_id=entry.session_id,
            organization_id=organization_id,
            queue_name=queue_name,
            operator_id=operator_id,
            claimed_at=time.time(),
            handoff=handoff,
        )

        redis = await self._get_redis()
        await redis.setex(
            self._claim_key(entry.session_id),
            self._handoff_ttl_s,
            json.dumps(claim.to_dict()),
        )
        logger.info(
            "operator {} claimed escalation session={} queue={}",
            operator_id,
            entry.session_id,
            queue_name,
        )
        return claim

    async def list_queue(
        self,
        organization_id: int,
        queue_name: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        items = await self._queues.list_queue(organization_id, queue_name, limit=limit)
        enriched: list[dict[str, Any]] = []
        for item in items:
            data = dict(item)
            session_id = data.get("session_id", "")
            handoff = await self.get_handoff(session_id)
            if handoff:
                data["handoff"] = handoff.to_dict()
            enriched.append(data)
        return enriched

    async def list_pending(
        self,
        organization_id: int,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        session_ids = await redis.smembers(self._org_index_key(organization_id))
        results: list[dict[str, Any]] = []
        for sid in list(session_ids)[:limit]:
            handoff = await self.get_handoff(sid)
            if not handoff:
                continue
            position = await self._queues.position(sid)
            claim_raw = await redis.get(self._claim_key(sid))
            results.append(
                {
                    "session_id": sid,
                    "handoff": handoff.to_dict(),
                    "queue_position": position,
                    "claimed": claim_raw is not None,
                    "claim": json.loads(claim_raw) if claim_raw else None,
                }
            )
        results.sort(key=lambda r: r["handoff"].get("priority", 0), reverse=True)
        return results

    async def resolve(self, session_id: str) -> bool:
        redis = await self._get_redis()
        handoff = await self.get_handoff(session_id)
        if handoff:
            await self._queues.remove(session_id)
            await redis.srem(self._org_index_key(handoff.organization_id), session_id)
        await redis.delete(self._handoff_key(session_id), self._claim_key(session_id))
        return True

    async def queue_depths(
        self,
        organization_id: int,
        queue_names: list[str],
    ) -> dict[str, int]:
        depths: dict[str, int] = {}
        for name in queue_names:
            depths[name] = await self._queues.depth(organization_id, name)
        return depths
