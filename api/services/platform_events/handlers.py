"""Built-in platform event handlers."""

from __future__ import annotations

from loguru import logger

from api.constants import CUSTOMER_TIMELINE_ENABLED, DURABLE_EXECUTION_ENABLED
from api.services.customer_timeline.indexer import TIMELINE_INDEXED_EVENT_TYPES
from api.services.platform_events.router import PlatformEventRouter
from api.services.platform_events.schema import PlatformEvent, PlatformEventType


async def _handle_payment_completed(event: PlatformEvent) -> None:
    if not DURABLE_EXECUTION_ENABLED:
        return
    transaction_id = event.payload.get("transaction_id")
    organization_id = event.organization_id
    if not transaction_id or organization_id is None:
        return

    from api.db import db_client
    from api.services.durable_execution.bridge import get_durable_execution_bridge
    from api.services.durable_execution.persistence import get_orchestration_persistence

    key = f"mpesa_payment_wait:txn:{transaction_id}"
    row = await get_orchestration_persistence().get_by_key(organization_id, key)
    if row is None:
        workflow_run_id = event.payload.get("workflow_run_id")
        if workflow_run_id:
            bridge = get_durable_execution_bridge()
            await bridge.start_mpesa_payment_wait(
                organization_id=organization_id,
                transaction_id=int(transaction_id),
                workflow_run_id=int(workflow_run_id),
            )
            row = await get_orchestration_persistence().get_by_key(organization_id, key)
        if row is None:
            return

    bridge = get_durable_execution_bridge()
    await bridge.signal_payment_completed(
        row.id,
        organization_id=organization_id,
        payload=event.payload,
    )
    logger.info(
        "payment.completed routed to durable orchestration orch_id={} txn={}",
        row.id,
        transaction_id,
    )


async def _handle_payment_failed(event: PlatformEvent) -> None:
    if not DURABLE_EXECUTION_ENABLED:
        return
    transaction_id = event.payload.get("transaction_id")
    organization_id = event.organization_id
    if not transaction_id or organization_id is None:
        return

    from api.services.durable_execution.bridge import get_durable_execution_bridge
    from api.services.durable_execution.persistence import get_orchestration_persistence

    key = f"mpesa_payment_wait:txn:{transaction_id}"
    row = await get_orchestration_persistence().get_by_key(organization_id, key)
    if row is None:
        return

    bridge = get_durable_execution_bridge()
    await bridge.signal_payment_failed(
        row.id,
        organization_id=organization_id,
        payload=event.payload,
    )


async def _handle_workflow_completed(event: PlatformEvent) -> None:
    """Delegate post-call follow-up to durable orchestration when enabled."""
    if not DURABLE_EXECUTION_ENABLED:
        return
    workflow_run_id = event.payload.get("workflow_run_id")
    organization_id = event.organization_id
    if not workflow_run_id or organization_id is None:
        return

    from api.services.durable_execution.bridge import maybe_start_post_call_durable

    await maybe_start_post_call_durable(int(workflow_run_id), organization_id)


async def _handle_campaign_retry_needed(event: PlatformEvent) -> None:
    logger.info(
        "campaign.retry_needed org={} campaign_id={} reason={}",
        event.organization_id,
        event.payload.get("campaign_id"),
        event.payload.get("reason"),
    )


async def _handle_timeline_index(event: PlatformEvent) -> None:
    if not CUSTOMER_TIMELINE_ENABLED:
        return
    from api.db import db_client
    from api.services.customer_timeline.indexer import get_customer_timeline_indexer

    row = await db_client.get_platform_event(event.event_id)
    await get_customer_timeline_indexer().index_platform_event(
        event,
        platform_event_db_id=row.id if row else None,
    )


async def _handle_escalation_created(event: PlatformEvent) -> None:
    logger.info(
        "escalation.created org={} session={} reason={}",
        event.organization_id,
        event.payload.get("session_id"),
        event.payload.get("reason"),
    )


def register_builtin_handlers(router: PlatformEventRouter) -> None:
    router.register(
        PlatformEventType.PAYMENT_COMPLETED,
        _handle_payment_completed,
        name="durable_mpesa_payment_completed",
    )
    router.register(
        PlatformEventType.PAYMENT_FAILED,
        _handle_payment_failed,
        name="durable_mpesa_payment_failed",
    )
    router.register(
        PlatformEventType.WORKFLOW_COMPLETED,
        _handle_workflow_completed,
        name="durable_post_call_workflow_completed",
    )
    router.register(
        PlatformEventType.CAMPAIGN_RETRY_NEEDED,
        _handle_campaign_retry_needed,
        name="campaign_retry_logger",
    )
    router.register(
        PlatformEventType.ESCALATION_CREATED,
        _handle_escalation_created,
        name="escalation_created_logger",
    )
    for event_type in TIMELINE_INDEXED_EVENT_TYPES:
        router.register(
            event_type,
            _handle_timeline_index,
            name=f"timeline_index_{event_type.value}",
        )
