"""Usage collectors for voice, WhatsApp, and M-Pesa."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.constants import TENANT_USAGE_BILLING_ENABLED
from api.db import db_client
from api.db.models import MpesaTransactionModel, WhatsAppMessageModel
from api.services.tenant_billing.ledger import get_usage_ledger
from api.services.tenant_billing.types import UsageMetric, UsageRecordRequest


class CallMinutesCollector:
    async def from_workflow_run(self, workflow_run_id: int) -> bool:
        if not TENANT_USAGE_BILLING_ENABLED:
            return False

        run = await db_client.get_workflow_run_by_id(workflow_run_id)
        if not run or not run.workflow:
            return False

        org_id = run.workflow.organization_id
        usage = run.usage_info or {}
        duration_s = usage.get("call_duration_seconds")
        try:
            minutes = float(duration_s) / 60.0
        except (TypeError, ValueError):
            return False
        if minutes <= 0:
            return False

        recorded = await get_usage_ledger().record(
            UsageRecordRequest(
                organization_id=org_id,
                metric=UsageMetric.CALL_MINUTES,
                quantity=round(minutes, 4),
                aggregation_key=f"workflow_run:{workflow_run_id}:call_minutes",
                workflow_run_id=workflow_run_id,
                metadata={"call_duration_seconds": duration_s},
            )
        )
        if recorded:
            await self._sync_stt_tts(run, org_id, workflow_run_id, usage)
            await self._sync_call_kind(run, org_id, workflow_run_id)
            await self._sync_llm(run, org_id, workflow_run_id, usage)
            await self._sync_storage(run, org_id, workflow_run_id)
        return recorded

    async def _sync_stt_tts(
        self,
        run: Any,
        org_id: int,
        workflow_run_id: int,
        usage: dict[str, Any],
    ) -> None:
        ledger = get_usage_ledger()
        stt_metrics = usage.get("stt") or {}
        total_stt = sum(float(v) for v in stt_metrics.values() if v)
        if total_stt > 0:
            await ledger.record(
                UsageRecordRequest(
                    organization_id=org_id,
                    metric=UsageMetric.STT_SECONDS,
                    quantity=round(total_stt, 2),
                    aggregation_key=f"workflow_run:{workflow_run_id}:stt",
                    workflow_run_id=workflow_run_id,
                    metadata={"breakdown": stt_metrics},
                )
            )

        tts_metrics = usage.get("tts") or {}
        total_tts = sum(int(v) for v in tts_metrics.values() if v)
        if total_tts > 0:
            await ledger.record(
                UsageRecordRequest(
                    organization_id=org_id,
                    metric=UsageMetric.TTS_CHARACTERS,
                    quantity=float(total_tts),
                    aggregation_key=f"workflow_run:{workflow_run_id}:tts",
                    workflow_run_id=workflow_run_id,
                    metadata={"breakdown": tts_metrics},
                )
            )

    async def _sync_call_kind(self, run: Any, org_id: int, workflow_run_id: int) -> None:
        from api.enums import WorkflowRunMode

        mode = str(getattr(run, "mode", "") or "")
        web_modes = {
            WorkflowRunMode.WEBRTC.value,
            WorkflowRunMode.SMALLWEBRTC.value,
            WorkflowRunMode.TEXTCHAT.value,
        }
        metric = UsageMetric.WEB_CALLS if mode in web_modes else UsageMetric.PHONE_CALLS
        await get_usage_ledger().record(
            UsageRecordRequest(
                organization_id=org_id,
                metric=metric,
                quantity=1.0,
                aggregation_key=f"workflow_run:{workflow_run_id}:{metric.value}",
                workflow_run_id=workflow_run_id,
                metadata={"mode": mode},
            )
        )

    async def _sync_llm(
        self, run: Any, org_id: int, workflow_run_id: int, usage: dict[str, Any]
    ) -> None:
        llm = usage.get("llm") or {}
        total = 0.0
        if isinstance(llm, dict):
            for item in llm.values():
                if isinstance(item, dict):
                    total += float(item.get("prompt_tokens") or 0)
                    total += float(item.get("completion_tokens") or 0)
        if total <= 0:
            return
        await get_usage_ledger().record(
            UsageRecordRequest(
                organization_id=org_id,
                metric=UsageMetric.LLM_TOKENS,
                quantity=total,
                aggregation_key=f"workflow_run:{workflow_run_id}:llm",
                workflow_run_id=workflow_run_id,
            )
        )

    async def _sync_storage(self, run: Any, org_id: int, workflow_run_id: int) -> None:
        extra = getattr(run, "extra", None) or {}
        bytes_used = extra.get("recording_bytes") or extra.get("storage_bytes")
        try:
            gb = float(bytes_used) / (1024**3)
        except (TypeError, ValueError):
            return
        if gb <= 0:
            return
        await get_usage_ledger().record(
            UsageRecordRequest(
                organization_id=org_id,
                metric=UsageMetric.STORAGE_GB,
                quantity=round(gb, 6),
                aggregation_key=f"workflow_run:{workflow_run_id}:storage",
                workflow_run_id=workflow_run_id,
            )
        )


class WhatsAppUsageCollector:
    async def from_message(
        self,
        *,
        organization_id: int,
        message: WhatsAppMessageModel,
    ) -> bool:
        if not TENANT_USAGE_BILLING_ENABLED:
            return False

        direction = (message.direction or "").lower()
        metric = (
            UsageMetric.WHATSAPP_INBOUND
            if direction == "inbound"
            else UsageMetric.WHATSAPP_OUTBOUND
        )
        return await get_usage_ledger().record(
            UsageRecordRequest(
                organization_id=organization_id,
                metric=metric,
                quantity=1.0,
                aggregation_key=f"whatsapp_message:{message.id}",
                reference_type="whatsapp_message",
                reference_id=str(message.id),
                metadata={
                    "conversation_id": message.conversation_id,
                    "template_name": message.template_name,
                },
            )
        )


class MpesaUsageCollector:
    async def from_transaction(self, tx: MpesaTransactionModel) -> bool:
        if not TENANT_USAGE_BILLING_ENABLED:
            return False

        status = (tx.status or "").lower()
        if status not in {"completed", "success"}:
            return False

        ledger = get_usage_ledger()
        await ledger.record(
            UsageRecordRequest(
                organization_id=tx.organization_id,
                metric=UsageMetric.MPESA_TRANSACTION,
                quantity=1.0,
                aggregation_key=f"mpesa_tx:{tx.id}:transaction",
                workflow_run_id=tx.workflow_run_id,
                reference_type="mpesa_transaction",
                reference_id=str(tx.id),
                metadata={"status": status},
            )
        )
        recorded = await ledger.record(
            UsageRecordRequest(
                organization_id=tx.organization_id,
                metric=UsageMetric.MPESA_COLLECTED,
                quantity=float(tx.amount),
                aggregation_key=f"mpesa_tx:{tx.id}:collected",
                workflow_run_id=tx.workflow_run_id,
                reference_type="mpesa_transaction",
                reference_id=str(tx.id),
                metadata={"currency": tx.currency},
            )
        )
        if recorded:
            from api.services.product_analytics import track_once

            await track_once(
                tx.organization_id,
                "first_payment",
                properties={"mpesa_transaction_id": tx.id},
            )
        return recorded


class TenantUsageCollectorService:
    """Facade invoked by workflow, WhatsApp, and M-Pesa hooks."""

    def __init__(self) -> None:
        self._calls = CallMinutesCollector()
        self._whatsapp = WhatsAppUsageCollector()
        self._mpesa = MpesaUsageCollector()

    async def collect_workflow_run(self, workflow_run_id: int) -> bool:
        try:
            return await self._calls.from_workflow_run(workflow_run_id)
        except Exception as e:
            logger.debug("workflow usage collect skipped run {}: {}", workflow_run_id, e)
            return False

    async def collect_whatsapp_message(
        self, *, organization_id: int, message: WhatsAppMessageModel
    ) -> bool:
        try:
            return await self._whatsapp.from_message(
                organization_id=organization_id, message=message
            )
        except Exception as e:
            logger.debug("whatsapp usage collect skipped msg {}: {}", message.id, e)
            return False

    async def collect_mpesa_transaction(self, tx: MpesaTransactionModel) -> bool:
        try:
            return await self._mpesa.from_transaction(tx)
        except Exception as e:
            logger.debug("mpesa usage collect skipped tx {}: {}", tx.id, e)
            return False


_service: TenantUsageCollectorService | None = None


def get_tenant_usage_collector() -> TenantUsageCollectorService:
    global _service
    if _service is None:
        _service = TenantUsageCollectorService()
    return _service
