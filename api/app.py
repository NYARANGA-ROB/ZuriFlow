"""Set up logging before importing anything else"""

import sentry_sdk

from api.constants import (
    APP_NAME,
    CORS_ALLOWED_ORIGINS,
    DEPLOYMENT_MODE,
    ENABLE_TELEMETRY,
    SENTRY_DSN,
)
from api.logging_config import ENVIRONMENT, setup_logging

# Set up logging and get the listener for cleanup
setup_logging()


if SENTRY_DSN and (
    DEPLOYMENT_MODE != "oss" or (DEPLOYMENT_MODE == "oss" and ENABLE_TELEMETRY)
):
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        send_default_pii=True,
        environment=ENVIRONMENT,
    )
    print(f"Sentry initialized in environment: {ENVIRONMENT}")


from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.constants import REDIS_URL
from api.mcp_server import mcp
from api.routes.main import router as main_router
from api.services.pipecat.tracing_config import (
    handle_langfuse_sync,
    load_all_org_langfuse_credentials,
)
from api.services.worker_sync.manager import (
    WorkerSyncManager,
    set_worker_sync_manager,
)
from api.services.worker_sync.protocol import WorkerSyncEventType
from api.tasks.arq import get_arq_redis

API_PREFIX = "/api/v1"

mcp_app = mcp.http_app(path="/", stateless_http=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from api.services.startup_validation import validate_production_config

    validate_production_config()

    async with mcp_app.lifespan(app):
        # warmup arq pool
        await get_arq_redis()

        # Pre-register all org-specific Langfuse exporters so they're ready
        # before any pipeline runs, without per-call DB lookups.
        await load_all_org_langfuse_credentials()

        # Start cross-worker sync manager so config changes propagate to all workers
        sync_manager = WorkerSyncManager(REDIS_URL)
        sync_manager.register(
            WorkerSyncEventType.LANGFUSE_CREDENTIALS, handle_langfuse_sync
        )
        await sync_manager.start()
        set_worker_sync_manager(sync_manager)

        from api.services.voice_analytics.pipeline import get_voice_analytics_pipeline

        await get_voice_analytics_pipeline().start()

        yield  # Run app

        await get_voice_analytics_pipeline().stop()

        from api.services.http_sessions import close_shared_http_session

        await close_shared_http_session()

        # Shutdown sequence - this runs when FastAPI is shutting down
        logger.info("Starting graceful shutdown...")
        await sync_manager.stop()


app = FastAPI(
    title=f"{APP_NAME} API",
    description=f"API for the {APP_NAME} app",
    version="1.0.0",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
    servers=[
        {"url": "https://app.dograh.com", "description": "Production"},
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
)


# Configure CORS.
# OSS is typically deployed with UI and API behind a single reverse proxy
# (same-origin, so CORS does not apply). Keep it permissive without
# credentials — wildcard + credentials is rejected by browsers and unsafe.
# SaaS deployments must set CORS_ALLOWED_ORIGINS to an explicit allowlist.
if DEPLOYMENT_MODE == "oss":
    cors_origins: list[str] = ["*"]
    cors_allow_credentials = False
else:
    if not CORS_ALLOWED_ORIGINS:
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS must be set to an explicit origin allowlist "
            "when DEPLOYMENT_MODE != 'oss'"
        )
    if "*" in CORS_ALLOWED_ORIGINS:
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS cannot contain '*' with credentialed requests"
        )
    cors_origins = CORS_ALLOWED_ORIGINS
    cors_allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _add_public_embed_cors_middleware() -> None:
    from api.routes.public_embed import PublicEmbedCORSMiddleware

    app.add_middleware(PublicEmbedCORSMiddleware, api_prefix=API_PREFIX)


_add_public_embed_cors_middleware()

from api.services.public_api.middleware import PublicApiGatewayMiddleware
from api.services.realtime_observability.middleware import RealtimeObservabilityMiddleware
from api.services.http_metrics.middleware import HttpMetricsMiddleware
from api.services.tenant.middleware import TenantMiddleware
from api.services.tenant_billing.middleware import TenantSubscriptionMiddleware
from api.services.voice_analytics.middleware import VoiceAnalyticsMiddleware

app.add_middleware(HttpMetricsMiddleware)
app.add_middleware(RealtimeObservabilityMiddleware)
app.add_middleware(VoiceAnalyticsMiddleware)
app.add_middleware(TenantSubscriptionMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(PublicApiGatewayMiddleware)

api_router = APIRouter()

# include subrouters here
api_router.include_router(main_router)

# main router with api prefix
app.include_router(api_router, prefix=API_PREFIX)

# Mount the MCP server — agents reach it at /api/v1/mcp over Streamable HTTP,
# authenticating with the same X-API-Key header used by the REST API.
# Mounted under /api/v1 so existing reverse-proxy rules (nginx etc.) route it
# without any extra configuration.
app.mount(f"{API_PREFIX}/mcp", mcp_app)
