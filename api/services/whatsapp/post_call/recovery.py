from __future__ import annotations

from typing import Any

from loguru import logger

from api.constants import WHATSAPP_RETRY_BASE_DELAY_S
from api.services.whatsapp.post_call.types import PostCallStep, PostCallWorkflowResult
from api.tasks.function_names import FunctionNames


class PostCallFailureRecovery:
    """Retry failed post-call workflow steps via ARQ."""

    def __init__(self, *, base_delay_s: float = WHATSAPP_RETRY_BASE_DELAY_S) -> None:
        self._base_delay_s = base_delay_s

    def _delay_for_attempt(self, attempt: int) -> int:
        return int(self._base_delay_s * (2 ** max(0, attempt - 1)))

    async def schedule_workflow_retry(
        self,
        *,
        workflow_run_id: int,
        resume_from_step: str | None,
        attempt: int,
        max_attempts: int,
    ) -> bool:
        if attempt >= max_attempts:
            logger.warning(
                "Post-call WhatsApp workflow exhausted retries run_id={} attempt={}",
                workflow_run_id,
                attempt,
            )
            return False

        from api.constants import DURABLE_EXECUTION_ENABLED

        if DURABLE_EXECUTION_ENABLED:
            try:
                from api.db import db_client
                from api.services.durable_execution.bridge import (
                    get_durable_execution_bridge,
                )

                organization_id = await db_client.get_organization_id_by_workflow_run_id(
                    workflow_run_id
                )
                if organization_id is not None:
                    bridge = get_durable_execution_bridge()
                    result = await bridge.start_post_call_whatsapp(
                        workflow_run_id=workflow_run_id,
                        organization_id=organization_id,
                        resume_from_step=resume_from_step,
                        attempt=attempt + 1,
                    )
                    if result is not None:
                        logger.info(
                            "Scheduled durable post-call retry orch_id={} run_id={} step={}",
                            result.orchestration_id,
                            workflow_run_id,
                            resume_from_step,
                        )
                        return True
            except Exception as exc:
                logger.warning(
                    "durable post-call retry fallback to ARQ run_id={}: {}",
                    workflow_run_id,
                    exc,
                )

        from api.tasks.arq import get_arq_redis

        redis = await get_arq_redis()
        delay = self._delay_for_attempt(attempt + 1)
        await redis.enqueue_job(
            FunctionNames.PROCESS_POST_CALL_WHATSAPP,
            workflow_run_id,
            resume_from_step,
            attempt + 1,
            _defer_by=delay,
        )
        logger.info(
            "Scheduled post-call WhatsApp retry run_id={} step={} attempt={} delay_s={}",
            workflow_run_id,
            resume_from_step,
            attempt + 1,
            delay,
        )
        return True

    def first_failed_step(self, result: PostCallWorkflowResult) -> PostCallStep | None:
        for step in result.steps:
            if not step.success:
                return step.step
        return None

    async def persist_workflow_state(
        self,
        *,
        conversation_id: int | None,
        workflow_run_id: int,
        result: PostCallWorkflowResult,
        attempt: int,
    ) -> None:
        if conversation_id is None:
            return
        from api.db import db_client

        conversation = await db_client.get_conversation(
            conversation_id,
            organization_id=result.organization_id,
        )
        if not conversation:
            return
        metadata = dict(conversation.metadata_json or {})
        metadata["post_call_workflow"] = {
            "workflow_run_id": workflow_run_id,
            "attempt": attempt,
            "result": result.to_dict(),
            "completed_steps": [s.step.value for s in result.steps if s.success],
            "failed_step": self.first_failed_step(result).value
            if self.first_failed_step(result)
            else None,
        }
        await db_client.get_or_create_conversation(
            organization_id=result.organization_id,
            phone_e164=conversation.phone_e164,
            provider=conversation.provider,
            workflow_run_id=workflow_run_id,
            metadata=metadata,
        )
