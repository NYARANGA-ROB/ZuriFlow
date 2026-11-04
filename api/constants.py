import os
from pathlib import Path

from api.enums import Environment

ENVIRONMENT = os.getenv("ENVIRONMENT", Environment.LOCAL.value)
# Absolute path to the project root directory (i.e. the directory containing
# the top-level api/ package). Having a single canonical location helps
# when constructing file-system paths elsewhere in the codebase.
APP_ROOT_DIR: Path = Path(__file__).resolve().parent

FILLER_SOUND_PROBABILITY = 0.0

VOICEMAIL_RECORDING_DURATION = 5.0

# Langfuse Configuration
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")

# URLs for deployment
BACKEND_API_ENDPOINT = os.getenv("BACKEND_API_ENDPOINT", "http://localhost:8000")
UI_APP_URL = os.getenv("UI_APP_URL", "http://localhost:3010")

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]

APP_NAME = os.getenv("APP_NAME", "ZuriFlow")

DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "oss")
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "local")
# Stack Auth public client config. These are safe to expose to the browser (the
# publishable client key is public by design, and the project id is non-sensitive),
# and are served to the UI at runtime via /api/v1/health so the frontend no longer
# needs them baked into the bundle at build time.
STACK_AUTH_PROJECT_ID = os.getenv("STACK_AUTH_PROJECT_ID")
STACK_PUBLISHABLE_CLIENT_KEY = os.getenv("STACK_PUBLISHABLE_CLIENT_KEY")
DOGRAH_MPS_SECRET_KEY = os.getenv("DOGRAH_MPS_SECRET_KEY", None)
MPS_API_URL = os.getenv("MPS_API_URL", "https://services.dograh.com")

# Storage Configuration
ENABLE_AWS_S3 = os.getenv("ENABLE_AWS_S3", "false").lower() == "true"

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "voice-audio")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# AWS S3 Configuration
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")

# Sentry configuration
SENTRY_DSN = os.getenv("SENTRY_DSN")

# PostHog configuration
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY")
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")


ENABLE_ARI_STASIS = os.getenv("ENABLE_ARI_STASIS", "false").lower() == "true"
SERIALIZE_LOG_OUTPUT = os.getenv("SERIALIZE_LOG_OUTPUT", "false").lower() == "true"

# Logging configuration
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", None)
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()

# Log rotation configuration
LOG_ROTATION_SIZE = os.getenv("LOG_ROTATION_SIZE", "100 MB")
LOG_RETENTION = os.getenv("LOG_RETENTION", "7 days")
LOG_COMPRESSION = os.getenv("LOG_COMPRESSION", "gz")
ENABLE_TELEMETRY = os.getenv("ENABLE_TELEMETRY", "false").lower() == "true"


def _get_version() -> str:
    """Read version from pyproject.toml."""
    try:
        import tomllib

        pyproject_path = APP_ROOT_DIR / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        return pyproject.get("project", {}).get("version", "dev")
    except Exception:
        return "dev"


# Application version (read from pyproject.toml)
APP_VERSION = _get_version()

# Country code mapping: ISO country code -> international dialing prefix
COUNTRY_CODES = {
    "US": "1",  # United States
    "CA": "1",  # Canada
    "GB": "44",  # United Kingdom
    "IN": "91",  # India
    "AU": "61",  # Australia
    "DE": "49",  # Germany
    "FR": "33",  # France
    "BR": "55",  # Brazil
    "MX": "52",  # Mexico
    "IT": "39",  # Italy
    "ES": "34",  # Spain
    "NL": "31",  # Netherlands
    "SE": "46",  # Sweden
    "NO": "47",  # Norway
    "DK": "45",  # Denmark
    "FI": "358",  # Finland
    "CH": "41",  # Switzerland
    "AT": "43",  # Austria
    "BE": "32",  # Belgium
    "LU": "352",  # Luxembourg
    "IE": "353",  # Ireland
}

DEFAULT_ORG_CONCURRENCY_LIMIT = os.getenv("DEFAULT_ORG_CONCURRENCY_LIMIT", 2)
DEFAULT_CAMPAIGN_RETRY_CONFIG = {
    "enabled": True,
    "max_retries": 1,
    "retry_delay_seconds": 120,
    "retry_on_busy": True,
    "retry_on_no_answer": True,
    "retry_on_voicemail": False,
}


# Circuit breaker defaults for campaign call failure detection
DEFAULT_CIRCUIT_BREAKER_CONFIG = {
    "enabled": True,
    "failure_threshold": 0.5,  # 50% failure rate trips the breaker
    "window_seconds": 120,  # 2-minute sliding window
    "min_calls_in_window": 5,  # Don't trip until at least 5 outcomes
}


TURN_SECRET = os.getenv("TURN_SECRET")
TURN_HOST = os.getenv("TURN_HOST", "localhost")
TURN_PORT = int(os.getenv("TURN_PORT", "3478"))
TURN_TLS_PORT = int(os.getenv("TURN_TLS_PORT", "5349"))
TURN_CREDENTIAL_TTL = int(os.getenv("TURN_CREDENTIAL_TTL", "86400"))
# Diagnostic flag: when true, strip all non-relay ICE candidates from the
# answer SDP so every media path must traverse the TURN server. Use for
# verifying TURN connectivity end-to-end; expect connection failures if
# TURN is misconfigured or unreachable.
FORCE_TURN_RELAY = os.getenv("FORCE_TURN_RELAY", "false").lower() == "true"

# Kenyan accent detection (optional ML stack — see api/requirements.kenyan-accent.txt)
KENYAN_ACCENT_ENABLED = os.getenv("KENYAN_ACCENT_ENABLED", "false").lower() == "true"
KENYAN_ACCENT_MODEL_PATH = os.getenv("KENYAN_ACCENT_MODEL_PATH") or None
PYANNOTE_AUTH_TOKEN = os.getenv("PYANNOTE_AUTH_TOKEN") or os.getenv("HF_TOKEN") or None

# Kenyan language normalization (Sheng / Swahili code-switch → English)
KENYAN_NORMALIZE_ENABLED = os.getenv("KENYAN_NORMALIZE_ENABLED", "true").lower() == "true"
KENYA_MARKET_LAYER_ENABLED = os.getenv("KENYA_MARKET_LAYER_ENABLED", "true").lower() == "true"
KENYAN_NORMALIZE_DICTIONARY_PATH = os.getenv("KENYAN_NORMALIZE_DICTIONARY_PATH") or None

# Kenyan conversational behavior for voice agents
KENYAN_CONVERSATION_ENABLED = os.getenv("KENYAN_CONVERSATION_ENABLED", "false").lower() == "true"
KENYAN_VOICE_PERSONALITY_ENABLED = os.getenv("KENYAN_VOICE_PERSONALITY_ENABLED", "true").lower() == "true"
KENYAN_CONVERSATION_LANGUAGE_MODE = os.getenv("KENYAN_CONVERSATION_LANGUAGE_MODE", "mixed")
KENYAN_CONVERSATION_DOMAIN = os.getenv("KENYAN_CONVERSATION_DOMAIN", "general")

# External credential encryption at rest (Fernet)
CREDENTIAL_ENCRYPTION_ENABLED = (
    os.getenv("CREDENTIAL_ENCRYPTION_ENABLED", "false").lower() == "true"
)
CREDENTIAL_ENCRYPTION_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")

# Telephony DTMF gather (inbound keypad → gathered_context.dtmf_digits)
DTMF_GATHER_ENABLED = os.getenv("DTMF_GATHER_ENABLED", "true").lower() == "true"

# Outbound telephony carrier failover across configuration rows
TELEPHONY_FAILOVER_ENABLED = (
    os.getenv("TELEPHONY_FAILOVER_ENABLED", "true").lower() == "true"
)

# LLM-driven IVR navigation (<dtmf> tags) on telephony calls
IVR_NAVIGATION_ENABLED = os.getenv("IVR_NAVIGATION_ENABLED", "true").lower() == "true"

# Realtime conversation memory for voice calls
REALTIME_MEMORY_ENABLED = os.getenv("REALTIME_MEMORY_ENABLED", "true").lower() == "true"
REALTIME_MEMORY_MAX_TURNS = int(os.getenv("REALTIME_MEMORY_MAX_TURNS", "12"))
REALTIME_MEMORY_SUMMARY_MAX_CHARS = int(os.getenv("REALTIME_MEMORY_SUMMARY_MAX_CHARS", "600"))
REALTIME_MEMORY_PAUSE_RECOVERY_S = float(os.getenv("REALTIME_MEMORY_PAUSE_RECOVERY_S", "8.0"))

# OSS Email/Password Auth
OSS_JWT_SECRET = os.getenv("OSS_JWT_SECRET", "change-me-in-production")
OSS_JWT_EXPIRY_HOURS = int(os.getenv("OSS_JWT_EXPIRY_HOURS", "720"))  # legacy access tokens
OSS_ACCESS_TOKEN_MINUTES = int(os.getenv("OSS_ACCESS_TOKEN_MINUTES", "60"))
OSS_REFRESH_TOKEN_DAYS = int(os.getenv("OSS_REFRESH_TOKEN_DAYS", "7"))
OSS_PASSWORD_MIN_LENGTH = int(os.getenv("OSS_PASSWORD_MIN_LENGTH", "12"))
LOGIN_RATE_LIMIT_MAX = int(os.getenv("LOGIN_RATE_LIMIT_MAX", "10"))
LOGIN_RATE_LIMIT_WINDOW_S = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_S", "60"))
LOGIN_LOCKOUT_THRESHOLD = int(os.getenv("LOGIN_LOCKOUT_THRESHOLD", "8"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))

TUNER_BASE_URL = os.getenv("TUNER_BASE_URL", "https://api.usetuner.ai")

# WhatsApp integration (org config overrides these defaults)
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
WHATSAPP_DEFAULT_PROVIDER = os.getenv("WHATSAPP_DEFAULT_PROVIDER", "meta")
WHATSAPP_RETRY_MAX_ATTEMPTS = int(os.getenv("WHATSAPP_RETRY_MAX_ATTEMPTS", "5"))
WHATSAPP_RETRY_BASE_DELAY_S = float(os.getenv("WHATSAPP_RETRY_BASE_DELAY_S", "30"))

# M-Pesa Daraja (Safaricom)
MPESA_ENABLED = os.getenv("MPESA_ENABLED", "false").lower() == "true"
MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox")
MPESA_RETRY_MAX_ATTEMPTS = int(os.getenv("MPESA_RETRY_MAX_ATTEMPTS", "5"))
MPESA_RETRY_BASE_DELAY_S = float(os.getenv("MPESA_RETRY_BASE_DELAY_S", "30"))
MPESA_STK_QUERY_DELAY_S = float(os.getenv("MPESA_STK_QUERY_DELAY_S", "45"))

# Voice-driven M-Pesa payment during calls
VOICE_MPESA_ENABLED = os.getenv("VOICE_MPESA_ENABLED", "false").lower() == "true"

# Kenyan realtime business intent detection
KENYAN_INTENT_ENABLED = os.getenv("KENYAN_INTENT_ENABLED", "true").lower() == "true"

# Intelligent call routing for voice agents
CALL_ROUTING_ENABLED = os.getenv("CALL_ROUTING_ENABLED", "true").lower() == "true"
CALL_ROUTING_QUEUE_TTL_S = int(os.getenv("CALL_ROUTING_QUEUE_TTL_S", "3600"))

# Voice workflow analytics
VOICE_ANALYTICS_ENABLED = os.getenv("VOICE_ANALYTICS_ENABLED", "true").lower() == "true"
VOICE_ANALYTICS_EVENT_TTL_S = int(os.getenv("VOICE_ANALYTICS_EVENT_TTL_S", str(86400 * 14)))
VOICE_ANALYTICS_MAX_EVENTS_PER_ORG = int(os.getenv("VOICE_ANALYTICS_MAX_EVENTS_PER_ORG", "10000"))

# Kenya production deployment profile (latency + cost tuning)
KENYA_PRODUCTION_MODE = os.getenv("KENYA_PRODUCTION_MODE", "false").lower() == "true"
ORG_CONFIG_CACHE_TTL_S = float(os.getenv("ORG_CONFIG_CACHE_TTL_S", "120"))
MPESA_STK_QUERY_DELAY_S_PROD = float(os.getenv("MPESA_STK_QUERY_DELAY_S_PROD", "35"))

# Vertical AI business-agent workflows
VERTICAL_WORKFLOWS_ENABLED = os.getenv("VERTICAL_WORKFLOWS_ENABLED", "true").lower() == "true"
AGENT_WIZARD_ENABLED = os.getenv("AGENT_WIZARD_ENABLED", "true").lower() == "true"
TEMPLATE_MARKETPLACE_ENABLED = os.getenv("TEMPLATE_MARKETPLACE_ENABLED", "true").lower() == "true"

# Kenyan debt collection AI workflow
DEBT_COLLECTION_ENABLED = os.getenv("DEBT_COLLECTION_ENABLED", "true").lower() == "true"
DEBT_COLLECTION_COMPLIANCE_ENABLED = (
    os.getenv("DEBT_COLLECTION_COMPLIANCE_ENABLED", "true").lower() == "true"
)
DEBT_COLLECTION_COMPLIANCE_AUDIT_TTL_S = int(
    os.getenv("DEBT_COLLECTION_COMPLIANCE_AUDIT_TTL_S", str(86400 * 30))
)

# Customer CRM
CRM_ENABLED = os.getenv("CRM_ENABLED", "true").lower() == "true"

# Predictive call prioritization for collection
CALL_PRIORITIZATION_ENABLED = os.getenv("CALL_PRIORITIZATION_ENABLED", "true").lower() == "true"
CALL_PRIORITIZATION_QUEUE_TTL_S = int(os.getenv("CALL_PRIORITIZATION_QUEUE_TTL_S", "86400"))

# Voice campaign management engine
VOICE_CAMPAIGN_ENABLED = os.getenv("VOICE_CAMPAIGN_ENABLED", "true").lower() == "true"

# Human escalation for AI voice agents
HUMAN_ESCALATION_ENABLED = os.getenv("HUMAN_ESCALATION_ENABLED", "true").lower() == "true"

# AI business call analytics (debt collection / vertical workflows)
BUSINESS_CALL_ANALYTICS_ENABLED = (
    os.getenv("BUSINESS_CALL_ANALYTICS_ENABLED", "true").lower() == "true"
)
BUSINESS_CALL_ANALYTICS_SNAPSHOT_TTL_S = int(
    os.getenv("BUSINESS_CALL_ANALYTICS_SNAPSHOT_TTL_S", str(86400 * 30))
)

# Conversation intelligence and executive BI dashboards
BUSINESS_INTELLIGENCE_ENABLED = (
    os.getenv("BUSINESS_INTELLIGENCE_ENABLED", "true").lower() == "true"
)

# Voice cost optimization (routing, caching, token budgets)
VOICE_COST_OPTIMIZATION_ENABLED = (
    os.getenv("VOICE_COST_OPTIMIZATION_ENABLED", "true").lower() == "true"
)
VOICE_COST_CACHE_TTL_S = int(os.getenv("VOICE_COST_CACHE_TTL_S", str(86400 * 7)))
VOICE_COST_SIMPLE_MAX_TOKENS = int(os.getenv("VOICE_COST_SIMPLE_MAX_TOKENS", "128"))
VOICE_COST_STANDARD_MAX_TOKENS = int(os.getenv("VOICE_COST_STANDARD_MAX_TOKENS", "384"))
VOICE_COST_COMPLEX_MAX_TOKENS = int(os.getenv("VOICE_COST_COMPLEX_MAX_TOKENS", "1024"))

# Call reliability and recovery
CALL_RELIABILITY_ENABLED = os.getenv("CALL_RELIABILITY_ENABLED", "true").lower() == "true"
CALL_RELIABILITY_MAX_RETRIES = int(os.getenv("CALL_RELIABILITY_MAX_RETRIES", "5"))
CALL_RELIABILITY_RETRY_BASE_DELAY_S = float(
    os.getenv("CALL_RELIABILITY_RETRY_BASE_DELAY_S", "30")
)
CALL_RELIABILITY_EVENT_TTL_S = int(
    os.getenv("CALL_RELIABILITY_EVENT_TTL_S", str(86400 * 14))
)
CALL_RELIABILITY_DLQ_TTL_S = int(
    os.getenv("CALL_RELIABILITY_DLQ_TTL_S", str(86400 * 30))
)
CALL_RELIABILITY_WS_CHECKPOINT_TTL_S = int(
    os.getenv("CALL_RELIABILITY_WS_CHECKPOINT_TTL_S", "300")
)

# Durable workflow orchestration
DURABLE_EXECUTION_ENABLED = os.getenv("DURABLE_EXECUTION_ENABLED", "true").lower() == "true"
DURABLE_EXECUTION_RETRY_BASE_DELAY_S = float(
    os.getenv("DURABLE_EXECUTION_RETRY_BASE_DELAY_S", "30")
)
DURABLE_EXECUTION_RECOVERY_INTERVAL_S = int(
    os.getenv("DURABLE_EXECUTION_RECOVERY_INTERVAL_S", "60")
)

# Platform event bus
PLATFORM_EVENTS_ENABLED = os.getenv("PLATFORM_EVENTS_ENABLED", "true").lower() == "true"
PLATFORM_EVENTS_DLQ_TTL_S = int(os.getenv("PLATFORM_EVENTS_DLQ_TTL_S", str(86400 * 30)))
PLATFORM_EVENTS_RETRY_BASE_DELAY_S = float(
    os.getenv("PLATFORM_EVENTS_RETRY_BASE_DELAY_S", "15")
)
PLATFORM_EVENTS_MAX_HANDLER_RETRIES = int(
    os.getenv("PLATFORM_EVENTS_MAX_HANDLER_RETRIES", "5")
)

# Unified customer engagement (voice + SMS + WhatsApp + web chat)
OMNICHANNEL_ENABLED = os.getenv("OMNICHANNEL_ENABLED", "true").lower() == "true"

# Omnichannel customer timeline
CUSTOMER_TIMELINE_ENABLED = os.getenv("CUSTOMER_TIMELINE_ENABLED", "true").lower() == "true"

# Multi-tenant isolation, RBAC, and billing context
TENANT_ISOLATION_ENABLED = os.getenv("TENANT_ISOLATION_ENABLED", "true").lower() == "true"

# Public API platform (gateway, rate limits, webhooks, usage analytics)
PUBLIC_API_ENABLED = os.getenv("PUBLIC_API_ENABLED", "true").lower() == "true"
PUBLIC_API_RATE_LIMIT_PER_ORG_PER_MIN = int(
    os.getenv("PUBLIC_API_RATE_LIMIT_PER_ORG_PER_MIN", "120")
)
PUBLIC_API_RATE_LIMIT_PER_KEY_PER_MIN = int(
    os.getenv("PUBLIC_API_RATE_LIMIT_PER_KEY_PER_MIN", "60")
)
PUBLIC_API_USAGE_TTL_S = int(os.getenv("PUBLIC_API_USAGE_TTL_S", str(86400 * 32)))
PUBLIC_API_WEBHOOK_DELIVERY_TIMEOUT_S = float(
    os.getenv("PUBLIC_API_WEBHOOK_DELIVERY_TIMEOUT_S", "10")
)

# Admin operations dashboard (unified analytics, search, realtime)
ADMIN_OPERATIONS_ENABLED = (
    os.getenv("ADMIN_OPERATIONS_ENABLED", "true").lower() == "true"
)
ADMIN_OPERATIONS_LIVE_POLL_S = float(
    os.getenv("ADMIN_OPERATIONS_LIVE_POLL_S", "5")
)
ADMIN_OPERATIONS_LIVE_TTL_S = int(
    os.getenv("ADMIN_OPERATIONS_LIVE_TTL_S", "3600")
)

# Multi-tenant usage billing and invoicing
TENANT_USAGE_BILLING_ENABLED = (
    os.getenv("TENANT_USAGE_BILLING_ENABLED", "true").lower() == "true"
)
TENANT_BILLING_DEFAULT_CURRENCY = os.getenv("TENANT_BILLING_DEFAULT_CURRENCY", "USD")
TENANT_BILLING_TAX_RATE = float(os.getenv("TENANT_BILLING_TAX_RATE", "0"))

# Commercial plan catalog (JSON). Prices must be supplied here — never hard-coded.
# Example: [{"id":"starter","display_name":"Starter","quotas":{"call_minutes_monthly":500}}]
ZURIFLOW_PLAN_CATALOG_JSON = os.getenv("ZURIFLOW_PLAN_CATALOG_JSON", "")

# Automated conversation quality evaluation
CONVERSATION_QUALITY_ENABLED = (
    os.getenv("CONVERSATION_QUALITY_ENABLED", "true").lower() == "true"
)

# Synthetic + production agent evaluation (not contractual SLAs)
AGENT_EVAL_ENABLED = os.getenv("AGENT_EVAL_ENABLED", "true").lower() == "true"

# Kenyan continuous learning pipeline
KENYAN_CONTINUOUS_LEARNING_ENABLED = (
    os.getenv("KENYAN_CONTINUOUS_LEARNING_ENABLED", "true").lower() == "true"
)
KENYAN_CL_DATA_PATH = os.getenv(
    "KENYAN_CL_DATA_PATH",
    str(Path(__file__).resolve().parent / "data" / "kenyan_continuous_learning"),
)

# On-prem local GPU inference routing
LOCAL_INFERENCE_ENABLED = (
    os.getenv("LOCAL_INFERENCE_ENABLED", "false").lower() == "true"
)
LOCAL_INFERENCE_ROUTES_JSON = os.getenv("LOCAL_INFERENCE_ROUTES", "")
INFERENCE_ROUTING_MODE = os.getenv("INFERENCE_ROUTING_MODE", "cloud")

# Business Digital Twin / live operations intelligence
BUSINESS_TWIN_ENABLED = os.getenv("BUSINESS_TWIN_ENABLED", "true").lower() == "true"
BUSINESS_TWIN_FRESHNESS_DAYS = int(os.getenv("BUSINESS_TWIN_FRESHNESS_DAYS", "30"))
BUSINESS_TWIN_STALE_DAYS = int(os.getenv("BUSINESS_TWIN_STALE_DAYS", "60"))
BUSINESS_TWIN_CRAWL_MAX_PAGES = int(os.getenv("BUSINESS_TWIN_CRAWL_MAX_PAGES", "20"))
BUSINESS_TWIN_CRAWL_TIMEOUT_S = float(os.getenv("BUSINESS_TWIN_CRAWL_TIMEOUT_S", "8"))
