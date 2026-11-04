from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from api.constants import CONVERSATION_QUALITY_ENABLED, CUSTOMER_TIMELINE_ENABLED, DURABLE_EXECUTION_ENABLED, KENYAN_CONTINUOUS_LEARNING_ENABLED, OMNICHANNEL_ENABLED, PLATFORM_EVENTS_ENABLED
from api.routes.omnichannel import router as omnichannel_router
from api.routes.customer_timeline import router as customer_timeline_router
from api.routes.durable_execution import router as durable_execution_router
from api.routes.control_plane import router as control_plane_router
from api.routes.conversation_quality import router as conversation_quality_router
from api.routes.agent_eval import router as agent_eval_router
from api.routes.kenyan_continuous_learning import router as kenyan_continuous_learning_router
from api.routes.tenant_billing import router as tenant_billing_router
from api.routes.admin_operations import router as admin_operations_router
from api.routes.template_marketplace import router as template_marketplace_router
from api.routes.agent_wizard import router as agent_wizard_router
from api.routes.agent_stream import router as agent_stream_router
from api.routes.auth import router as auth_router
from api.routes.call_routing import router as call_routing_router
from api.routes.human_escalation import router as human_escalation_router
from api.routes.voice_campaign import router as voice_campaign_router
from api.routes.call_prioritization import router as call_prioritization_router
from api.routes.crm import router as crm_router
from api.routes.call_reliability import router as call_reliability_router
from api.routes.business_twin import router as business_twin_router
from api.routes.business_intelligence import router as business_intelligence_router
from api.routes.business_call_analytics import router as business_call_analytics_router
from api.routes.debt_collection import router as debt_collection_router
from api.routes.campaign import router as campaign_router
from api.routes.credentials import router as credentials_router
from api.routes.folder import router as folder_router
from api.routes.kenya import router as kenya_router
from api.constants import KENYAN_ACCENT_ENABLED
from api.routes.kenyan_voice_personality import router as kenyan_voice_personality_router
from api.routes.kenyan_conversation import router as kenyan_conversation_router
from api.routes.kenyan_intent import router as kenyan_intent_router
from api.routes.kenyan_normalize import router as kenyan_normalize_router
from api.routes.realtime_memory import router as realtime_memory_router
from api.routes.knowledge_base import router as knowledge_base_router
from api.routes.node_types import router as node_types_router
from api.routes.organization import router as organization_router
from api.routes.organization_usage import router as organization_usage_router
from api.routes.public_agent import router as public_agent_router
from api.routes.public_download import router as public_download_router
from api.routes.public_api import router as public_api_router
from api.routes.public_embed import router as public_embed_router
from api.routes.realtime_audio import router as realtime_audio_router
from api.routes.realtime_observability import router as realtime_observability_router
from api.routes.realtime_voice import router as realtime_voice_router
from api.routes.reports import router as reports_router
from api.routes.s3_signed_url import router as s3_router
from api.routes.service_keys import router as service_keys_router
from api.routes.superuser import router as superuser_router
from api.routes.telephony import router as telephony_router
from api.routes.tenant import router as tenant_router
from api.routes.tool import router as tool_router
from api.routes.turn_credentials import router as turn_credentials_router
from api.routes.user import router as user_router
from api.routes.webrtc_signaling import router as webrtc_signaling_router
from api.routes.workflow import router as workflow_router
from api.routes.workflow_embed import router as workflow_embed_router
from api.routes.workflow_recording import router as workflow_recording_router
from api.routes.workflow_text_chat import router as workflow_text_chat_router
from api.routes.voice_cost_optimization import router as voice_cost_optimization_router
from api.routes.voice_analytics import router as voice_analytics_router
from api.routes.vertical_workflows import router as vertical_workflows_router
from api.routes.whatsapp import router as whatsapp_router
from api.services.integrations import all_routers

router = APIRouter(
    tags=["main"],
    responses={404: {"description": "Not found"}},
)

router.include_router(telephony_router)
router.include_router(superuser_router)
router.include_router(workflow_router)
router.include_router(workflow_text_chat_router)
router.include_router(user_router)
router.include_router(campaign_router)
router.include_router(credentials_router)
router.include_router(tool_router)
router.include_router(organization_router)
router.include_router(tenant_router)
router.include_router(tenant_billing_router)
router.include_router(s3_router)
router.include_router(service_keys_router)
router.include_router(organization_usage_router)
router.include_router(reports_router)
router.include_router(webrtc_signaling_router)
router.include_router(realtime_audio_router)
router.include_router(realtime_voice_router)
router.include_router(realtime_observability_router)
if KENYAN_ACCENT_ENABLED:
    from api.routes.kenyan_accent import router as kenyan_accent_router

    router.include_router(kenyan_accent_router)
router.include_router(kenyan_normalize_router)
router.include_router(kenyan_intent_router)
router.include_router(call_routing_router)
router.include_router(human_escalation_router)
router.include_router(voice_campaign_router)
router.include_router(call_prioritization_router)
router.include_router(crm_router)
router.include_router(debt_collection_router)
router.include_router(call_reliability_router)
router.include_router(business_intelligence_router)
router.include_router(business_twin_router)
router.include_router(business_call_analytics_router)
router.include_router(admin_operations_router)
if DURABLE_EXECUTION_ENABLED:
    router.include_router(durable_execution_router)
if PLATFORM_EVENTS_ENABLED:
    from api.routes.platform_events import router as platform_events_router

    router.include_router(platform_events_router)
if CUSTOMER_TIMELINE_ENABLED:
    router.include_router(customer_timeline_router)
if OMNICHANNEL_ENABLED:
    router.include_router(omnichannel_router)
router.include_router(control_plane_router)
router.include_router(conversation_quality_router)
router.include_router(agent_eval_router)
if KENYAN_CONTINUOUS_LEARNING_ENABLED:
    router.include_router(kenyan_continuous_learning_router)
router.include_router(voice_cost_optimization_router)
router.include_router(voice_analytics_router)
router.include_router(vertical_workflows_router)
router.include_router(kenyan_voice_personality_router)
router.include_router(kenyan_conversation_router)
router.include_router(realtime_memory_router)
router.include_router(whatsapp_router)
router.include_router(kenya_router)
router.include_router(mpesa_router)
router.include_router(turn_credentials_router)
router.include_router(public_embed_router)
router.include_router(public_api_router)
router.include_router(public_agent_router)
router.include_router(public_download_router)
router.include_router(workflow_embed_router)
router.include_router(knowledge_base_router)
router.include_router(workflow_recording_router)
router.include_router(folder_router)
router.include_router(auth_router)
router.include_router(node_types_router)
router.include_router(template_marketplace_router)
router.include_router(agent_wizard_router)
router.include_router(agent_stream_router)

for _integration_router in all_routers():
    router.include_router(_integration_router)


class HealthResponse(BaseModel):
    status: str
    version: str
    backend_api_endpoint: str
    deployment_mode: str
    auth_provider: str
    turn_enabled: bool
    force_turn_relay: bool
    # Public Stack Auth client config — only populated when auth_provider == "stack".
    # The UI reads these at runtime to initialize Stack, so they no longer need to
    # be baked into the browser bundle at build time. Both are public values.
    stack_project_id: str | None = None
    stack_publishable_client_key: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from api.constants import (
        APP_VERSION,
        AUTH_PROVIDER,
        DEPLOYMENT_MODE,
        FORCE_TURN_RELAY,
        STACK_AUTH_PROJECT_ID,
        STACK_PUBLISHABLE_CLIENT_KEY,
        TURN_SECRET,
    )
    from api.utils.common import get_backend_endpoints

    logger.debug("Health endpoint called")
    backend_endpoint, _ = await get_backend_endpoints()
    is_stack = AUTH_PROVIDER == "stack"
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        backend_api_endpoint=backend_endpoint,
        deployment_mode=DEPLOYMENT_MODE,
        auth_provider=AUTH_PROVIDER,
        turn_enabled=bool(TURN_SECRET),
        force_turn_relay=FORCE_TURN_RELAY,
        stack_project_id=STACK_AUTH_PROJECT_ID if is_stack else None,
        stack_publishable_client_key=(
            STACK_PUBLISHABLE_CLIENT_KEY if is_stack else None
        ),
    )


class ReadinessResponse(BaseModel):
    ready: bool
    checks: dict


@router.get("/health/ready", response_model=ReadinessResponse)
async def health_ready() -> ReadinessResponse:
    from api.services.health_checks import readiness_report

    report = await readiness_report()
    if not report["ready"]:
        raise HTTPException(status_code=503, detail=report)
    return ReadinessResponse(**report)
