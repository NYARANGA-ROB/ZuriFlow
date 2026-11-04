from api.db.admin_operations_client import AdminOperationsClient
from api.db.agent_eval_client import AgentEvalClient
from api.db.agent_setup_client import AgentSetupClient
from api.db.agent_trigger_client import AgentTriggerClient
from api.db.api_key_client import APIKeyClient
from api.db.business_call_analytics_client import BusinessCallAnalyticsClient
from api.db.business_intelligence_client import BusinessIntelligenceClient
from api.db.business_twin_client import BusinessTwinClient
from api.db.campaign_client import CampaignClient
from api.db.customer_timeline_client import CustomerTimelineClient
from api.db.control_plane_client import ControlPlaneClient
from api.db.conversation_quality_client import ConversationQualityClient
from api.db.crm_client import CrmClient
from api.db.durable_orchestration_client import DurableOrchestrationClient
from api.db.embed_token_client import EmbedTokenClient
from api.db.folder_client import FolderClient
from api.db.integration_client import IntegrationClient
from api.db.kenya_intelligence_client import KenyaIntelligenceClient
from api.db.kenyan_continuous_learning_client import KenyanContinuousLearningClient
from api.db.knowledge_base_client import KnowledgeBaseClient
from api.db.mpesa_client import MpesaClient
from api.db.omnichannel_client import OmnichannelClient
from api.db.organization_client import OrganizationClient
from api.db.organization_configuration_client import OrganizationConfigurationClient
from api.db.organization_usage_client import OrganizationUsageClient
from api.db.platform_event_client import PlatformEventClient
from api.db.product_analytics_client import ProductAnalyticsClient
from api.db.public_api_client import PublicApiClient
from api.db.reports_client import ReportsClient
from api.db.security_audit_client import SecurityAuditClient
from api.db.telephony_configuration_client import TelephonyConfigurationClient
from api.db.telephony_phone_number_client import TelephonyPhoneNumberClient
from api.db.tenant_billing_client import TenantBillingClient
from api.db.tenant_client import TenantClient
from api.db.tool_client import ToolClient
from api.db.user_client import UserClient
from api.db.webhook_credential_client import WebhookCredentialClient
from api.db.whatsapp_client import WhatsAppClient
from api.db.workflow_client import WorkflowClient
from api.db.workflow_recording_client import WorkflowRecordingClient
from api.db.workflow_run_client import WorkflowRunClient
from api.db.workflow_run_text_session_client import WorkflowRunTextSessionClient
from api.db.workflow_template_client import WorkflowTemplateClient


class DBClient(
    AgentEvalClient,
    AdminOperationsClient,
    AgentSetupClient,
    BusinessTwinClient,
    WorkflowClient,
    WorkflowRunClient,
    WorkflowRunTextSessionClient,
    UserClient,
    OrganizationClient,
    OrganizationConfigurationClient,
    OrganizationUsageClient,
    PlatformEventClient,
    BusinessCallAnalyticsClient,
    IntegrationClient,
    WorkflowTemplateClient,
    CampaignClient,
    ReportsClient,
    APIKeyClient,
    EmbedTokenClient,
    AgentTriggerClient,
    WebhookCredentialClient,
    ToolClient,
    KnowledgeBaseClient,
    WorkflowRecordingClient,
    TelephonyConfigurationClient,
    TelephonyPhoneNumberClient,
    FolderClient,
    WhatsAppClient,
    MpesaClient,
    CrmClient,
    ControlPlaneClient,
    BusinessIntelligenceClient,
    ConversationQualityClient,
    CustomerTimelineClient,
    DurableOrchestrationClient,
    KenyanContinuousLearningClient,
    KenyaIntelligenceClient,
    TenantClient,
    TenantBillingClient,
    PublicApiClient,
    ProductAnalyticsClient,
    OmnichannelClient,
    SecurityAuditClient,
):
    """
    Unified database client that combines all specialized database operations.

    This client inherits from:
    - WorkflowClient: handles workflow and workflow definition operations
    - WorkflowRunClient: handles workflow run operations
    - UserClient: handles user and user configuration operations
    - OrganizationClient: handles organization operations
    - OrganizationConfigurationClient: handles organization configuration operations
    - OrganizationUsageClient: handles organization usage reporting aggregates
    - IntegrationClient: handles integration operations
    - WorkflowTemplateClient: handles workflow template operations
    - CampaignClient: handles campaign operations
    - ReportsClient: handles reports and analytics operations
    - APIKeyClient: handles API key operations
    - EmbedTokenClient: handles embed token and session operations
    - AgentTriggerClient: handles agent trigger operations for API-based call triggering
    - WebhookCredentialClient: handles webhook credential operations
    - ToolClient: handles tool operations for reusable HTTP API tools
    - KnowledgeBaseClient: handles knowledge base document and vector search operations
    - FolderClient: handles folder operations for grouping workflows (agents)
    """

    pass
