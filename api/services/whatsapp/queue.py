from __future__ import annotations

from api.constants import WHATSAPP_RETRY_BASE_DELAY_S, WHATSAPP_RETRY_MAX_ATTEMPTS
from api.services.whatsapp.types import OutboundPayload
from api.tasks.function_names import FunctionNames


class WhatsAppRetryQueue:
    """Enqueue outbound WhatsApp sends with exponential backoff via ARQ."""

    def __init__(
        self,
        *,
        max_attempts: int = WHATSAPP_RETRY_MAX_ATTEMPTS,
        base_delay_s: float = WHATSAPP_RETRY_BASE_DELAY_S,
    ) -> None:
        self._max_attempts = max_attempts
        self._base_delay_s = base_delay_s

    def _delay_for_attempt(self, attempt: int) -> int:
        return int(self._base_delay_s * (2 ** max(0, attempt - 1)))

    async def enqueue_send(self, payload: OutboundPayload) -> None:
        from api.tasks.arq import enqueue_job

        await enqueue_job(
            FunctionNames.SEND_WHATSAPP_MESSAGE,
            payload.__dict__,
        )

    async def enqueue_retry(self, payload: OutboundPayload) -> bool:
        if payload.attempt >= self._max_attempts:
            return False
        retry_payload = OutboundPayload(
            organization_id=payload.organization_id,
            phone_e164=payload.phone_e164,
            body=payload.body,
            provider=payload.provider,
            template_name=payload.template_name,
            conversation_id=payload.conversation_id,
            message_id=payload.message_id,
            workflow_run_id=payload.workflow_run_id,
            metadata=payload.metadata,
            attempt=payload.attempt + 1,
        )
        delay = self._delay_for_attempt(retry_payload.attempt)
        from api.tasks.arq import get_arq_redis

        redis = await get_arq_redis()
        await redis.enqueue_job(
            FunctionNames.SEND_WHATSAPP_MESSAGE,
            retry_payload.__dict__,
            _defer_by=delay,
        )
        return True
