"""ARQ worker configuration - setup logging before importing tasks"""

import ssl
from urllib.parse import urlparse

from api.constants import REDIS_URL

# Setup logging - this is now idempotent and safe to call multiple times
from api.logging_config import setup_logging
from api.tasks.function_names import FunctionNames

setup_logging()

# Now import ARQ and task dependencies
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.cron import cron

parsed_url = urlparse(REDIS_URL)

# Check if we're using TLS (rediss://)
use_ssl = parsed_url.scheme == "rediss"

# Create SSL context if using rediss://
ssl_context = None
if use_ssl:
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

REDIS_SETTINGS = RedisSettings(
    host=parsed_url.hostname or "localhost",
    port=parsed_url.port or 6379,
    password=parsed_url.password,
    conn_timeout=10,
    ssl=use_ssl,
    ssl_ca_certs=None if not use_ssl else None,
    ssl_certfile=None,
    ssl_keyfile=None,
    ssl_check_hostname=False if use_ssl else None,
)

from api.tasks.platform_event_tasks import (
    process_platform_event_retries,
    route_platform_event,
)
from api.tasks.durable_execution_tasks import (
    process_all_durable_scheduled_tasks,
    process_durable_orchestration_task,
    recover_stale_durable_orchestrations,
)
from api.tasks.call_routing_tasks import (
    process_call_routing_escalation,
    process_call_routing_queue_timeout,
)
from api.tasks.call_reliability_tasks import (
    process_all_call_reliability_retries,
    process_call_reliability_retries,
)
from api.tasks.business_call_analytics_tasks import (
    aggregate_all_business_call_analytics,
    aggregate_business_call_analytics,
)
from api.tasks.voice_analytics_tasks import (
    aggregate_all_voice_analytics,
    aggregate_voice_analytics,
    ingest_voice_analytics_event,
)
from api.tasks.campaign_tasks import (
    process_campaign_batch,
    sync_campaign_source,
)
from api.tasks.kenyan_learning_tasks import run_kenyan_continuous_learning_training
from api.tasks.knowledge_base_processing import process_knowledge_base_document
from api.tasks.run_integrations import run_integrations_post_workflow_run
from api.tasks.s3_upload import upload_voicemail_audio_to_s3
from api.tasks.mpesa_tasks import (
    process_mpesa_callback,
    verify_all_pending_mpesa_transactions,
    verify_mpesa_transaction,
)
from api.tasks.voice_mpesa_tasks import voice_mpesa_complete_payment, voice_mpesa_send_receipt
from api.tasks.whatsapp_post_call_tasks import process_post_call_whatsapp
from api.tasks.whatsapp_tasks import send_whatsapp_message
from api.tasks.business_twin_tasks import (
    process_business_event,
    process_due_business_syncs,
    sync_business_source,
)
from api.tasks.agent_eval_tasks import run_agent_eval_suite
from api.tasks.workflow_completion import process_workflow_completion


class WorkerSettings:
    functions = [
        run_integrations_post_workflow_run,
        upload_voicemail_audio_to_s3,
        process_workflow_completion,
        sync_campaign_source,
        process_campaign_batch,
        process_knowledge_base_document,
        send_whatsapp_message,
        process_post_call_whatsapp,
        process_mpesa_callback,
        verify_mpesa_transaction,
        voice_mpesa_send_receipt,
        voice_mpesa_complete_payment,
        process_call_routing_escalation,
        process_call_routing_queue_timeout,
        ingest_voice_analytics_event,
        aggregate_voice_analytics,
        aggregate_all_voice_analytics,
        aggregate_business_call_analytics,
        aggregate_all_business_call_analytics,
        process_call_reliability_retries,
        process_all_call_reliability_retries,
        verify_all_pending_mpesa_transactions,
        run_kenyan_continuous_learning_training,
        process_durable_orchestration_task,
        process_all_durable_scheduled_tasks,
        recover_stale_durable_orchestrations,
        route_platform_event,
        process_platform_event_retries,
        run_agent_eval_suite,
        sync_business_source,
        process_business_event,
        process_due_business_syncs,
    ]
    cron_jobs = [
        cron(process_all_call_reliability_retries, minute=set(range(60)), second=0),
        cron(process_all_durable_scheduled_tasks, minute=set(range(60)), second=15),
        cron(recover_stale_durable_orchestrations, minute=set(range(60)), second=30),
        cron(process_platform_event_retries, minute=set(range(60)), second=45),
        cron(verify_all_pending_mpesa_transactions, minute={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58}),
        cron(process_due_business_syncs, minute={0, 15, 30, 45}, second=20),
    ]
    redis_settings = REDIS_SETTINGS
    max_jobs = 10


LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    # --- Handlers ---
    "handlers": {
        "console": {  # everything goes to stdout
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "level": "WARNING",  # only WARNING and above
            "formatter": "simple",
        },
    },
    # --- Formatters (optional) ---
    "formatters": {
        "simple": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        },
    },
    # --- Root logger ---
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    # --- Optionally silence Arq itself explicitly ---
    "loggers": {
        "arq": {  # arq.* loggers
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}


_redis_pool: ArqRedis | None = None


async def get_arq_redis() -> ArqRedis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await create_pool(REDIS_SETTINGS)
    return _redis_pool


async def enqueue_job(function_name: FunctionNames, *args):
    redis = await get_arq_redis()
    await redis.enqueue_job(function_name, *args)
