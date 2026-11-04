import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    func,
    text,
)
from sqlalchemy.orm import declarative_base, relationship

from api.constants import DEFAULT_CAMPAIGN_RETRY_CONFIG

from ..enums import (
    CallType,
    IntegrationAction,
    ToolCategory,
    ToolStatus,
    TriggerState,
    WebhookCredentialType,
    WorkflowRunState,
    WorkflowStatus,
)

Base = declarative_base()


# TODO: remove workflow_defintion after migration, remove nullable workflow_defintion_id from Workflow and Workflowrun


# Association table for many-to-many relationship between users and organizations
organization_users_association = Table(
    "organization_users",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column(
        "organization_id", Integer, ForeignKey("organizations.id"), primary_key=True
    ),
)


class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    workflows = relationship("WorkflowModel", back_populates="user")
    selected_organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True
    )
    selected_organization = relationship("OrganizationModel", back_populates="users")
    organizations = relationship(
        "OrganizationModel",
        secondary=organization_users_association,
        back_populates="users",
    )
    is_superuser = Column(Boolean, default=False)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)

    __table_args__ = (
        Index(
            "ix_users_email_lower",
            func.lower(email),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
    )


class UserConfigurationModel(Base):
    """Per-user keyed JSON store, mirroring organization_configurations.

    Keys are defined in UserConfigurationKey. The legacy v1 AI model
    configuration lives under MODEL_CONFIGURATION; last_validated_at is only
    meaningful for that key.
    """

    __tablename__ = "user_configurations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    key = Column(String, nullable=False)
    configuration = Column(JSON, nullable=False, default=dict)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="_user_configuration_key_uc"),
    )


# New Organization model
class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Deprecated: MPS owns quota and credit ledger state.
    quota_type = Column(
        Enum("monthly", "annual", name="quota_type"),
        nullable=False,
        default="monthly",
        server_default=text("'monthly'::quota_type"),
        comment="Deprecated. MPS owns quota and credit ledger state.",
        info={"deprecated": True},
    )
    quota_dograh_tokens = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Deprecated. MPS owns quota and credit ledger state.",
        info={"deprecated": True},
    )
    quota_reset_day = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Deprecated. MPS owns quota and credit ledger state.",
        info={"deprecated": True},
    )
    quota_start_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Deprecated. MPS owns quota and credit ledger state.",
        info={"deprecated": True},
    )
    quota_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Deprecated. MPS owns quota and credit ledger state.",
        info={"deprecated": True},
    )

    price_per_second_usd = Column(Float, nullable=True)

    # Relationships
    users = relationship(
        "UserModel",
        secondary=organization_users_association,
        back_populates="organizations",
    )
    integrations = relationship("IntegrationModel", back_populates="organization")
    usage_cycles = relationship(
        "OrganizationUsageCycleModel", back_populates="organization"
    )
    configurations = relationship(
        "OrganizationConfigurationModel", back_populates="organization"
    )
    api_keys = relationship("APIKeyModel", back_populates="organization")
    members = relationship("OrganizationMemberModel", back_populates="organization")
    webhook_subscriptions = relationship(
        "WebhookSubscriptionModel", back_populates="organization"
    )
    agent_setup_sessions = relationship(
        "AgentSetupSessionModel", back_populates="organization"
    )


class AgentSetupSessionModel(Base):
    """Self-serve agent wizard onboarding session."""

    __tablename__ = "agent_setup_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String(36), unique=True, index=True, nullable=False)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    state = Column(String(32), nullable=False, default="industry", server_default="industry")
    config = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True)
    phone_number_id = Column(
        Integer,
        ForeignKey("telephony_phone_numbers.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message = Column(String(512), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    organization = relationship("OrganizationModel", back_populates="agent_setup_sessions")
    user = relationship("UserModel")
    workflow = relationship("WorkflowModel")
    phone_number = relationship("TelephonyPhoneNumberModel")

    __table_args__ = (
        Index("ix_agent_setup_sessions_org_user", "organization_id", "user_id"),
        Index("ix_agent_setup_sessions_state", "state"),
    )


class OrganizationMemberModel(Base):
    """Per-organization membership with RBAC role."""

    __tablename__ = "organization_members"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False, default="viewer", server_default="viewer")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    organization = relationship("OrganizationModel", back_populates="members")
    user = relationship("UserModel")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="_organization_member_uc"),
        Index("ix_organization_members_org_id", "organization_id"),
        Index("ix_organization_members_user_id", "user_id"),
    )


class APIKeyModel(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String, nullable=False)
    key_hash = Column(String, nullable=False, unique=True, index=True)
    key_prefix = Column(String, nullable=False)  # Store first 8 chars for display
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("OrganizationModel", back_populates="api_keys")
    created_by_user = relationship("UserModel")

    # Indexes for performance
    __table_args__ = (
        Index("ix_api_keys_organization_id", "organization_id"),
        Index("ix_api_keys_key_hash", "key_hash"),
        Index("ix_api_keys_active", "is_active"),
    )


class WebhookSubscriptionModel(Base):
    """Outbound webhook endpoint registered by an organization for platform events."""

    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    subscription_uuid = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=False)
    events = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    organization = relationship("OrganizationModel", back_populates="webhook_subscriptions")

    __table_args__ = (
        Index("ix_webhook_subscriptions_org_id", "organization_id"),
        Index("ix_webhook_subscriptions_active", "is_active"),
    )


class OrganizationConfigurationModel(Base):
    __tablename__ = "organization_configurations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    key = Column(String, nullable=False)
    value = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    organization = relationship("OrganizationModel", back_populates="configurations")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="_organization_key_uc"),
        Index("ix_organization_configurations_organization_id", "organization_id"),
    )


class TelephonyConfigurationModel(Base):
    __tablename__ = "telephony_configurations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(64), nullable=False)
    provider = Column(String(32), nullable=False)
    credentials = Column(JSON, nullable=False, default=dict)
    is_default_outbound = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    organization = relationship("OrganizationModel")
    phone_numbers = relationship(
        "TelephonyPhoneNumberModel",
        back_populates="configuration",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_telephony_configurations_org_name"
        ),
        Index("ix_telephony_configurations_org", "organization_id"),
        Index(
            "uq_telephony_configurations_default",
            "organization_id",
            unique=True,
            postgresql_where=text("is_default_outbound = true"),
        ),
    )


class TelephonyPhoneNumberModel(Base):
    __tablename__ = "telephony_phone_numbers"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    telephony_configuration_id = Column(
        Integer,
        ForeignKey("telephony_configurations.id", ondelete="CASCADE"),
        nullable=False,
    )
    address = Column(String(255), nullable=False)
    address_normalized = Column(String(255), nullable=False)
    address_type = Column(String(16), nullable=False)
    country_code = Column(String(2), nullable=True)
    label = Column(String(64), nullable=True)
    inbound_workflow_id = Column(
        Integer,
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_default_caller_id = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    extra_metadata = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    configuration = relationship(
        "TelephonyConfigurationModel", back_populates="phone_numbers"
    )
    inbound_workflow = relationship("WorkflowModel")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "address_normalized",
            name="uq_phone_numbers_org_address",
        ),
        Index("ix_phone_numbers_config", "telephony_configuration_id"),
        Index(
            "ix_phone_numbers_workflow",
            "inbound_workflow_id",
            postgresql_where=text("inbound_workflow_id IS NOT NULL"),
        ),
        Index(
            "ix_phone_numbers_inbound_lookup",
            "address_normalized",
            "organization_id",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "uq_phone_numbers_default_caller",
            "telephony_configuration_id",
            unique=True,
            postgresql_where=text("is_default_caller_id = true"),
        ),
    )


class IntegrationModel(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(
        String, nullable=False, index=True
    )  # External connection ID
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    provider = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    connection_details = Column(JSON, nullable=False, default=dict)
    action = Column(String, nullable=False, default=IntegrationAction.ALL_CALLS.value)

    # Relationships
    organization = relationship("OrganizationModel", back_populates="integrations")


class WorkflowDefinitionModel(Base):
    __tablename__ = "workflow_definitions"
    id = Column(Integer, primary_key=True, index=True)
    workflow_hash = Column(String, nullable=True)  # Legacy, no longer used
    workflow_json = Column(JSON, nullable=False, default=dict)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    is_current = Column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Versioning columns
    status = Column(
        String,
        nullable=False,
        default="published",
        server_default=text("'published'"),
    )  # draft | published | archived
    version_number = Column(
        Integer, nullable=True
    )  # Sequential per workflow, display only
    published_at = Column(DateTime(timezone=True), nullable=True)
    changelog = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    published_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Full behavioral snapshot (moved from WorkflowModel to enable versioning)
    workflow_configurations = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    template_context_variables = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )

    # Table constraints and indexes — unique hash constraint removed (no more dedup)
    __table_args__ = (
        Index("ix_workflow_definitions_workflow_status", "workflow_id", "status"),
    )

    # Relationships
    workflow = relationship(
        "WorkflowModel",
        back_populates="definitions",
        foreign_keys=[workflow_id],
    )
    workflow_runs = relationship("WorkflowRunModel", back_populates="definition")


class FolderModel(Base):
    """A folder for grouping workflows (agents) within an organization.

    Folders are flat (no nesting) and org-scoped. A workflow belongs to at
    most one folder via ``WorkflowModel.folder_id``; a NULL folder_id means
    the workflow is "Uncategorized".
    """

    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    organization = relationship("OrganizationModel")
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    workflows = relationship("WorkflowModel", back_populates="folder")

    # Folder names must be unique within an organization.
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_folder_org_name"),
    )


class WorkflowModel(Base):
    __tablename__ = "workflows"
    id = Column(Integer, primary_key=True, index=True)
    workflow_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("UserModel", back_populates="workflows")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("OrganizationModel")
    # Optional folder for grouping in the agents list. NULL = "Uncategorized".
    # ON DELETE SET NULL: deleting a folder un-files its agents, never deletes them.
    folder_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    folder = relationship("FolderModel", back_populates="workflows")
    name = Column(String, index=True, nullable=False)
    status = Column(
        Enum(*[status.value for status in WorkflowStatus], name="workflow_status"),
        nullable=False,
        default=WorkflowStatus.ACTIVE.value,
        server_default=text("'active'::workflow_status"),
    )
    workflow_definition = Column(JSON, nullable=False, default=dict)
    template_context_variables = Column(JSON, nullable=False, default=dict)
    call_disposition_codes = Column(JSON, nullable=False, default=dict)
    workflow_configurations = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    runs = relationship("WorkflowRunModel", back_populates="workflow")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Pointer to the currently-live (published) version
    released_definition_id = Column(
        Integer,
        ForeignKey("workflow_definitions.id", use_alter=True),
        nullable=True,
    )
    released_definition = relationship(
        "WorkflowDefinitionModel",
        foreign_keys=[released_definition_id],
        uselist=False,
        viewonly=True,
    )

    # All versions / historical definitions of this workflow
    definitions = relationship(
        "WorkflowDefinitionModel",
        back_populates="workflow",
        foreign_keys="WorkflowDefinitionModel.workflow_id",
    )

    # Relationship to fetch the current (is_current=True) definition
    # Kept for backward compatibility during transition
    current_definition = relationship(
        "WorkflowDefinitionModel",
        primaryjoin=lambda: and_(
            WorkflowDefinitionModel.workflow_id == WorkflowModel.id,
            WorkflowDefinitionModel.is_current.is_(True),
        ),
        uselist=False,
        viewonly=True,
    )

    @property
    def current_definition_id(self):
        """Return ID of the current workflow definition (helper for backwards-compat)."""
        current_def = self.__dict__.get("current_definition")
        if current_def is not None:
            return current_def.id

        # If relationship is not loaded, we cannot safely access definitions without
        # risking an implicit lazy load on a detached instance. Return ``None`` in
        # that scenario so callers can handle the absence explicitly.
        return None


class WorkflowTemplates(Base):
    __tablename__ = "workflow_templates"
    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String, nullable=False, index=True)
    template_description = Column(String, nullable=False, index=True)
    template_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class WorkflowRunModel(Base):
    __tablename__ = "workflow_runs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    workflow = relationship("WorkflowModel", back_populates="runs")
    definition_id = Column(
        Integer, ForeignKey("workflow_definitions.id"), nullable=True
    )
    definition = relationship("WorkflowDefinitionModel", back_populates="workflow_runs")
    # Stored as VARCHAR (not a Postgres ENUM) so new telephony providers can
    # be added purely in application code without a database migration.
    # See WorkflowRunMode in api/enums.py for the canonical value set.
    mode = Column(String(64), nullable=False)
    call_type = Column(
        Enum(*[call_type.value for call_type in CallType], name="workflow_call_type"),
        nullable=False,
        default=CallType.OUTBOUND.value,
        server_default=text("'outbound'::workflow_call_type"),
    )
    state = Column(
        Enum(*[state.value for state in WorkflowRunState], name="workflow_run_state"),
        nullable=False,
        default=WorkflowRunState.INITIALIZED.value,
        server_default=text("'initialized'::workflow_run_state"),
    )
    is_completed = Column(Boolean, default=False)
    recording_url = Column(String, nullable=True)
    transcript_url = Column(String, nullable=True)
    extra = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    # Store storage backend as string enum (s3, minio)
    storage_backend = Column(
        Enum("s3", "minio", name="storage_backend"),
        nullable=False,
        default="s3",
        server_default=text("'s3'::storage_backend"),
    )
    usage_info = Column(JSON, nullable=False, default=dict)
    cost_info = Column(JSON, nullable=False, default=dict)
    initial_context = Column(JSON, nullable=False, default=dict)
    gathered_context = Column(JSON, nullable=False, default=dict)
    logs = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    annotations = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    campaign = relationship("CampaignModel")
    queued_run_id = Column(Integer, ForeignKey("queued_runs.id"), nullable=True)
    queued_run = relationship("QueuedRunModel", foreign_keys=[queued_run_id])
    public_access_token = Column(String(36), nullable=True)
    text_session = relationship(
        "WorkflowRunTextSessionModel",
        back_populates="workflow_run",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index(
            "idx_workflow_runs_public_access_token",
            "public_access_token",
            unique=True,
            postgresql_where=text("public_access_token IS NOT NULL"),
        ),
        Index(
            "idx_workflow_runs_call_id",
            text("(gathered_context->>'call_id')"),
            postgresql_where=text("gathered_context->>'call_id' IS NOT NULL"),
        ),
        Index("idx_workflow_runs_workflow_id", "workflow_id"),
        Index("idx_workflow_runs_campaign_id", "campaign_id"),
    )


class WorkflowRunTextSessionModel(Base):
    __tablename__ = "workflow_run_text_sessions"

    workflow_run_id = Column(
        Integer,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    workflow_run = relationship("WorkflowRunModel", back_populates="text_session")
    revision = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    session_data = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    checkpoint = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_workflow_run_text_sessions_updated_at", "updated_at"),)


class WhatsAppConversationModel(Base):
    __tablename__ = "whatsapp_conversations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    phone_e164 = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    status = Column(String, nullable=False, server_default=text("'active'"))
    escalated = Column(Boolean, nullable=False, server_default=text("false"))
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    messages = relationship(
        "WhatsAppMessageModel",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "phone_e164",
            "provider",
            name="uq_whatsapp_conversations_org_phone_provider",
        ),
        Index("ix_whatsapp_conversations_org_updated", "organization_id", "updated_at"),
    )


class WhatsAppMessageModel(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    template_name = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default=text("'pending'"))
    provider_message_id = Column(String, nullable=True)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    conversation = relationship("WhatsAppConversationModel", back_populates="messages")

    __table_args__ = (
        Index("ix_whatsapp_messages_conversation_created", "conversation_id", "created_at"),
    )


class MpesaTransactionModel(Base):
    __tablename__ = "mpesa_transactions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    phone_e164 = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, server_default=text("'KES'"))
    account_reference = Column(String, nullable=False)
    transaction_desc = Column(String, nullable=False)
    merchant_request_id = Column(String, nullable=True)
    checkout_request_id = Column(String, nullable=True, unique=True)
    mpesa_receipt_number = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default=text("'pending'"))
    result_code = Column(Integer, nullable=True)
    result_desc = Column(String, nullable=True)
    attempt_count = Column(Integer, nullable=False, server_default=text("0"))
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    callback_payload = Column(JSON, nullable=True)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    events = relationship(
        "MpesaTransactionEventModel",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_mpesa_transactions_org_status", "organization_id", "status"),
        Index("ix_mpesa_transactions_org_created", "organization_id", "created_at"),
        Index(
            "ix_mpesa_transactions_receipt",
            "mpesa_receipt_number",
            postgresql_where=text("mpesa_receipt_number IS NOT NULL"),
        ),
    )


class MpesaTransactionEventModel(Base):
    __tablename__ = "mpesa_transaction_events"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(
        Integer,
        ForeignKey("mpesa_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String, nullable=False)
    payload = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    transaction = relationship("MpesaTransactionModel", back_populates="events")

    __table_args__ = (
        Index("ix_mpesa_transaction_events_tx_created", "transaction_id", "created_at"),
    )


class OrganizationUsageCycleModel(Base):
    """
    This model is used to track reporting aggregates for an organization for a given
    usage cycle. Quota fields on this model are deprecated; MPS owns quota and
    credit ledger state.
    """

    __tablename__ = "organization_usage_cycles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    quota_dograh_tokens = Column(
        Integer,
        nullable=False,
        comment="Deprecated. MPS owns quota and credit ledger state.",
        info={"deprecated": True},
    )
    used_dograh_tokens = Column(Float, nullable=False, default=0)
    total_duration_seconds = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    # New USD tracking fields
    used_amount_usd = Column(Float, nullable=True, default=0)
    quota_amount_usd = Column(
        Float,
        nullable=True,
        comment="Deprecated. MPS owns quota and credit ledger state.",
        info={"deprecated": True},
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    organization = relationship("OrganizationModel", back_populates="usage_cycles")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "period_start", "period_end", name="unique_org_period"
        ),
        Index("idx_usage_cycles_org_period", "organization_id", "period_end"),
    )


class CampaignModel(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Nullable during the legacy → multi-config migration window. Backfilled to the
    # org's default config by the migration; will become NOT NULL in a follow-up.
    telephony_configuration_id = Column(
        Integer, ForeignKey("telephony_configurations.id"), nullable=True
    )

    # Source configuration
    source_type = Column(String, nullable=False, default="csv")
    source_id = Column(String, nullable=False)  # CSV file key

    # State management
    state = Column(
        Enum(
            "created",
            "syncing",
            "running",
            "paused",
            "completed",
            "failed",
            "cancelled",
            name="campaign_state",
        ),
        nullable=False,
        default="created",
    )

    # Progress tracking
    total_rows = Column(Integer, nullable=True)
    processed_rows = Column(Integer, nullable=False, default=0)
    failed_rows = Column(Integer, nullable=False, default=0)

    # Rate limiting and sync configuration
    rate_limit_per_second = Column(Integer, nullable=False, default=1)
    max_retries = Column(Integer, nullable=False, default=0)
    source_sync_status = Column(String, nullable=False, default="pending")
    source_last_synced_at = Column(DateTime(timezone=True), nullable=True)
    source_sync_error = Column(String, nullable=True)

    # Retry configuration for call failures
    retry_config = Column(
        JSON,
        nullable=False,
        default=DEFAULT_CAMPAIGN_RETRY_CONFIG,
        server_default=text(
            '\'{"enabled": true, "max_retries": 2, "retry_on_busy": true, "retry_on_no_answer": true, "retry_on_voicemail": true, "retry_delay_seconds": 120}\'::jsonb'
        ),
    )

    # Orchestrator tracking fields
    last_batch_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    orchestrator_metadata = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )

    # Append-only timestamped log entries for state transitions, failures,
    # and circuit-breaker events. Surfaced in the UI so operators can see
    # why a campaign moved to paused/failed without digging through logs.
    logs = Column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    organization = relationship("OrganizationModel")
    workflow = relationship("WorkflowModel")
    created_by_user = relationship("UserModel")

    # Indexes
    __table_args__ = (
        Index("ix_campaigns_org_id", "organization_id"),
        Index("ix_campaigns_state", "state"),
        Index("ix_campaigns_workflow_id", "workflow_id"),
        Index(
            "ix_campaigns_telephony_config",
            "telephony_configuration_id",
            postgresql_where=text("telephony_configuration_id IS NOT NULL"),
        ),
        # Index for efficient querying of active campaigns
        Index(
            "idx_campaigns_active_status",
            "state",
            postgresql_where=text("state IN ('syncing', 'running', 'paused')"),
        ),
    )


class QueuedRunModel(Base):
    __tablename__ = "queued_runs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    source_uuid = Column(String, nullable=False)
    context_variables = Column(JSON, nullable=False, default=dict)
    state = Column(
        Enum("queued", "processed", "processing", "failed", name="queued_run_state"),
        nullable=False,
        default="queued",
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # New retry-related fields
    retry_count = Column(Integer, default=0, nullable=False, server_default=text("0"))
    parent_queued_run_id = Column(Integer, ForeignKey("queued_runs.id"), nullable=True)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    retry_reason = Column(String, nullable=True)  # 'busy', 'no_answer', 'voicemail'

    # Relationships
    campaign = relationship("CampaignModel")
    parent_queued_run = relationship("QueuedRunModel", remote_side=[id])

    # Indexes
    __table_args__ = (
        Index("idx_queued_runs_campaign_state", "campaign_id", "state"),
        Index("idx_queued_runs_created", "created_at"),
        Index("idx_queued_runs_source_uuid", "source_uuid"),
        Index(
            "idx_queued_runs_scheduled", "scheduled_for"
        ),  # New index for scheduled retries
        # Optimized index for checking queued runs efficiently
        Index(
            "idx_queued_runs_campaign_state_optimized",
            "campaign_id",
            "state",
            postgresql_where=text("state = 'queued'"),
        ),
        # Optimized index for scheduled retries
        Index(
            "idx_queued_runs_scheduled_optimized",
            "campaign_id",
            "scheduled_for",
            postgresql_where=text("scheduled_for IS NOT NULL"),
        ),
        UniqueConstraint(
            "campaign_id",
            "source_uuid",
            "retry_count",
            name="unique_campaign_source_retry",
        ),
    )


class EmbedTokenModel(Base):
    """Model for storing workflow embed tokens"""

    __tablename__ = "embed_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    workflow_id = Column(
        Integer,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    allowed_domains = Column(JSON, nullable=True)  # Array of whitelisted domains
    settings = Column(JSON, nullable=True)  # Widget customization settings
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    usage_limit = Column(Integer, nullable=True)  # Optional usage limit
    usage_count = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    created_by = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    workflow = relationship("WorkflowModel")
    organization = relationship("OrganizationModel")
    creator = relationship("UserModel")
    sessions = relationship(
        "EmbedSessionModel", back_populates="embed_token", cascade="all, delete-orphan"
    )


class EmbedSessionModel(Base):
    """Model for storing temporary embed sessions"""

    __tablename__ = "embed_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    embed_token_id = Column(
        Integer, ForeignKey("embed_tokens.id", ondelete="CASCADE"), nullable=False
    )
    workflow_run_id = Column(
        Integer, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=True
    )
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    origin = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    embed_token = relationship("EmbedTokenModel", back_populates="sessions")
    workflow_run = relationship("WorkflowRunModel")


class AgentTriggerModel(Base):
    """Model for storing agent trigger mappings (UUID -> workflow_id).

    This is a minimal lookup table that maps trigger UUIDs to workflows.
    The trigger node in the workflow definition is the source of truth.
    """

    __tablename__ = "agent_triggers"

    id = Column(Integer, primary_key=True, index=True)

    # Globally unique trigger path (UUID format)
    trigger_path = Column(String(36), unique=True, nullable=False, index=True)

    # Link to workflow
    workflow_id = Column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # State management (active/archived)
    state = Column(
        Enum(*[state.value for state in TriggerState], name="trigger_state"),
        nullable=False,
        default=TriggerState.ACTIVE.value,
        server_default=text("'active'::trigger_state"),
    )

    # Audit
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    workflow = relationship("WorkflowModel")
    organization = relationship("OrganizationModel")

    # Indexes for performance
    __table_args__ = (
        Index("ix_agent_triggers_workflow_id", "workflow_id"),
        Index("ix_agent_triggers_state", "state"),
    )


class ExternalCredentialModel(Base):
    """Model for storing external authentication credentials.

    Credentials are stored separately from webhook configurations to allow
    reuse across multiple workflows and secure storage of sensitive data.
    """

    __tablename__ = "external_credentials"

    id = Column(Integer, primary_key=True, index=True)

    # Public UUID reference (used in APIs and workflow definitions)
    # This prevents enumeration attacks and hides internal IDs
    credential_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Organization scoping
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Credential metadata
    name = Column(String, nullable=False)  # Display name, e.g., "Salesforce API"
    description = Column(String, nullable=True)  # Optional description

    # Credential type - uses enum from api/enums.py
    credential_type = Column(
        Enum(
            *[t.value for t in WebhookCredentialType],
            name="webhook_credential_type",
        ),
        nullable=False,
        default=WebhookCredentialType.NONE.value,
    )

    # Encrypted credential data (JSON)
    # Structure depends on credential_type:
    # - api_key: {"header_name": "X-API-Key", "api_key": "value"}
    # - bearer_token: {"token": "value"}
    # - basic_auth: {"username": "user", "password": "value"}
    # - custom_header: {"header_name": "X-Custom", "header_value": "value"}
    credential_data = Column(JSON, nullable=False, default=dict)

    # Audit fields
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Soft delete for safety
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    organization = relationship("OrganizationModel")
    created_by_user = relationship("UserModel")

    # Indexes and constraints
    __table_args__ = (
        Index("ix_webhook_credentials_organization_id", "organization_id"),
        Index("ix_webhook_credentials_uuid", "credential_uuid"),
        UniqueConstraint("organization_id", "name", name="unique_org_credential_name"),
    )


class ToolModel(Base):
    """Model for storing reusable tools that can be invoked during workflows.

    Tools provide a standardized way to integrate external functionality - from
    HTTP API calls to native integrations.
    """

    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)

    # Public identifier (used in APIs and workflow references)
    tool_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Organization scoping
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Tool metadata
    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)

    # Tool category - uses enum from api/enums.py
    category = Column(
        Enum(
            *[c.value for c in ToolCategory],
            name="tool_category",
        ),
        nullable=False,
        default=ToolCategory.HTTP_API.value,
    )

    # Icon configuration (for UI display)
    icon = Column(String(50), nullable=True)  # Icon identifier
    icon_color = Column(String(7), nullable=True)  # Hex color code

    # Status management
    status = Column(
        Enum(
            *[s.value for s in ToolStatus],
            name="tool_status",
        ),
        nullable=False,
        default=ToolStatus.ACTIVE.value,
        server_default=text("'active'::tool_status"),
    )

    # The tool definition (JSONB) - contains schema_version for compatibility
    # Structure depends on category:
    # - http_api: {"schema_version": 1, "type": "http_api", "config": {...}}
    definition = Column(JSON, nullable=False, default=dict)

    # Audit fields
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    organization = relationship("OrganizationModel")
    created_by_user = relationship("UserModel")

    # Indexes and constraints
    __table_args__ = (
        Index("ix_tools_organization_id", "organization_id"),
        Index("ix_tools_uuid", "tool_uuid"),
        Index("ix_tools_status", "status"),
        Index("ix_tools_category", "category"),
    )


class KnowledgeBaseDocumentModel(Base):
    """Model for storing document-level metadata in the knowledge base.

    Each document represents a source file (PDF, DOCX, etc.) that has been
    processed and chunked for retrieval.
    """

    __tablename__ = "knowledge_base_documents"

    id = Column(Integer, primary_key=True, index=True)

    # Public identifier for API references
    document_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Organization scoping
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Document metadata
    filename = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    file_hash = Column(String(64), nullable=True)  # SHA-256 hash for deduplication
    mime_type = Column(String(100), nullable=True)

    # Retrieval mode: "chunked" (vector search) or "full_document" (return full text)
    retrieval_mode = Column(
        String(20), nullable=False, default="chunked", server_default="chunked"
    )
    full_text = Column(
        Text, nullable=True
    )  # Stored when retrieval_mode is "full_document"

    # Processing metadata
    source_url = Column(String, nullable=True)  # If document was fetched from URL
    total_chunks = Column(Integer, nullable=False, default=0)
    processing_status = Column(
        Enum(
            "pending",
            "processing",
            "completed",
            "failed",
            name="document_processing_status",
        ),
        nullable=False,
        default="pending",
        server_default=text("'pending'::document_processing_status"),
    )
    processing_error = Column(Text, nullable=True)

    # Docling conversion metadata
    docling_metadata = Column(
        JSON, nullable=False, default=dict
    )  # Store docling document metadata

    # Custom metadata (user-defined tags, categories, etc.)
    custom_metadata = Column(JSON, nullable=False, default=dict)

    # Audit fields
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Soft delete
    is_active = Column(Boolean, default=True, nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("OrganizationModel")
    created_by_user = relationship("UserModel")
    chunks = relationship(
        "KnowledgeBaseChunkModel",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_kb_documents_organization_id", "organization_id"),
        Index("ix_kb_documents_uuid", "document_uuid"),
        Index("ix_kb_documents_status", "processing_status"),
        Index("ix_kb_documents_created_at", "created_at"),
    )


class WorkflowRecordingModel(Base):
    """Model for storing audio recordings scoped to an organization.

    Recordings are used in hybrid prompts where parts of the output are pre-recorded
    audio rather than dynamically generated TTS.
    """

    __tablename__ = "workflow_recordings"

    id = Column(Integer, primary_key=True, index=True)

    # Descriptive ID used in prompts (unique per organization)
    recording_id = Column(String(64), nullable=False, index=True)

    # Scoping
    workflow_id = Column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=True
    )
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # TTS configuration metadata (optional, legacy)
    tts_provider = Column(String, nullable=True)
    tts_model = Column(String, nullable=True)
    tts_voice_id = Column(String, nullable=True)

    # Content
    transcript = Column(Text, nullable=False)

    # Storage
    storage_key = Column(String, nullable=False)
    storage_backend = Column(
        Enum("s3", "minio", name="recording_storage_backend"),
        nullable=False,
        default="s3",
        server_default=text("'s3'::recording_storage_backend"),
    )

    # Extra metadata (file_size_bytes, duration_seconds, original_filename, mime_type, etc.)
    recording_metadata = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )

    # Audit
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Soft delete
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    workflow = relationship("WorkflowModel")
    organization = relationship("OrganizationModel")
    created_by_user = relationship("UserModel")

    # Indexes
    __table_args__ = (
        UniqueConstraint(
            "recording_id",
            "organization_id",
            name="uq_workflow_recordings_recording_id_org",
        ),
        Index("ix_workflow_recordings_workflow_id", "workflow_id"),
        Index("ix_workflow_recordings_org_id", "organization_id"),
        Index("ix_workflow_recordings_recording_id", "recording_id"),
    )


class KnowledgeBaseChunkModel(Base):
    """Model for storing document chunks with vector embeddings.

    Each chunk represents a portion of a document that has been:
    1. Extracted and chunked by docling's HybridChunker
    2. Optionally contextualized with surrounding information
    3. Embedded into a vector representation for semantic search
    """

    __tablename__ = "knowledge_base_chunks"

    id = Column(Integer, primary_key=True, index=True)

    # Link to parent document
    document_id = Column(
        Integer,
        ForeignKey("knowledge_base_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Organization scoping (denormalized for efficient querying)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Chunk content
    chunk_text = Column(Text, nullable=False)  # The actual chunk text
    contextualized_text = Column(
        Text, nullable=True
    )  # Enriched text from chunker.contextualize()

    # Chunk positioning and metadata
    chunk_index = Column(Integer, nullable=False)  # Position in document (0-based)

    # Docling chunk metadata
    chunk_metadata = Column(
        JSON, nullable=False, default=dict
    )  # Store chunk.meta if available

    # Embedding configuration
    embedding_model = Column(
        String(200), nullable=False
    )  # e.g., "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension = Column(
        Integer, nullable=False
    )  # e.g., 384 for all-MiniLM-L6-v2

    # Vector embedding (pgvector column)
    # The dimension should match the embedding_dimension field
    # Default: 1536 dimensions for OpenAI text-embedding-3-small
    # SentenceTransformer (384-dim) also supported but stored as 384-dim vectors
    embedding = Column(Vector(1536), nullable=True)

    # Token count (useful for chunking strategy analysis)
    token_count = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    document = relationship("KnowledgeBaseDocumentModel", back_populates="chunks")
    organization = relationship("OrganizationModel")

    # Indexes and constraints
    __table_args__ = (
        Index("ix_kb_chunks_document_id", "document_id"),
        Index("ix_kb_chunks_organization_id", "organization_id"),
        Index("ix_kb_chunks_chunk_index", "chunk_index"),
        Index(
            "ix_kb_chunks_embedding_model", "embedding_model"
        ),  # For filtering by model
        # Vector similarity search index (using IVFFlat or HNSW)
        # IVFFlat is good for datasets with 10k-1M vectors
        # HNSW is better for larger datasets but uses more memory
        Index(
            "ix_kb_chunks_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},  # Adjust based on dataset size
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# ---------------------------------------------------------------------------
# Customer CRM
# ---------------------------------------------------------------------------


class CustomerModel(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    customer_uuid = Column(
        String,
        nullable=False,
        unique=True,
        default=lambda: str(uuid.uuid4()),
    )
    external_crm_id = Column(String, nullable=True)
    phone_e164 = Column(String, nullable=False)
    phone_original = Column(String, nullable=True)
    email = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    preferred_locale = Column(String, nullable=False, server_default=text("'mixed'"))
    secondary_locales = Column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    debt_accounts = relationship(
        "CustomerDebtAccountModel",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    payments = relationship(
        "CustomerPaymentModel",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    call_history = relationship(
        "CustomerCallHistoryModel",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    escalations = relationship(
        "CustomerEscalationHistoryModel",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "phone_e164",
            name="uq_customers_org_phone",
        ),
        Index("ix_customers_org_external_crm", "organization_id", "external_crm_id"),
        Index("ix_customers_org_name", "organization_id", "full_name"),
    )


class CustomerDebtAccountModel(Base):
    __tablename__ = "customer_debt_accounts"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    account_reference = Column(String, nullable=False)
    outstanding_balance = Column(Float, nullable=False, server_default=text("0"))
    currency = Column(String, nullable=False, server_default=text("'KES'"))
    days_past_due = Column(Integer, nullable=False, server_default=text("0"))
    minimum_settlement = Column(Float, nullable=True)
    status = Column(String, nullable=False, server_default=text("'active'"))
    last_payment_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    customer = relationship("CustomerModel", back_populates="debt_accounts")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "account_reference",
            name="uq_customer_debt_org_account_ref",
        ),
        Index("ix_customer_debt_org_status", "organization_id", "status"),
        Index("ix_customer_debt_customer", "customer_id"),
    )


class CustomerPaymentModel(Base):
    __tablename__ = "customer_payments"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    debt_account_id = Column(
        Integer,
        ForeignKey("customer_debt_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    mpesa_transaction_id = Column(
        Integer,
        ForeignKey("mpesa_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, server_default=text("'KES'"))
    payment_method = Column(String, nullable=False, server_default=text("'mpesa'"))
    status = Column(String, nullable=False, server_default=text("'pending'"))
    receipt_reference = Column(String, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    customer = relationship("CustomerModel", back_populates="payments")

    __table_args__ = (
        Index("ix_customer_payments_org_customer", "organization_id", "customer_id"),
        Index("ix_customer_payments_org_paid_at", "organization_id", "paid_at"),
    )


class CustomerCallHistoryModel(Base):
    __tablename__ = "customer_call_history"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    call_type = Column(String, nullable=False, server_default=text("'outbound'"))
    phone_e164 = Column(String, nullable=False)
    duration_s = Column(Float, nullable=True)
    disposition = Column(String, nullable=True)
    outcome = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    language = Column(String, nullable=False, server_default=text("'mixed'"))
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    customer = relationship("CustomerModel", back_populates="call_history")

    __table_args__ = (
        Index("ix_customer_calls_org_customer", "organization_id", "customer_id"),
        Index("ix_customer_calls_workflow_run", "workflow_run_id"),
    )


class CustomerEscalationHistoryModel(Base):
    __tablename__ = "customer_escalation_history"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    session_id = Column(String, nullable=True)
    reason = Column(String, nullable=False)
    risk_level = Column(String, nullable=False, server_default=text("'medium'"))
    queue_name = Column(String, nullable=True)
    resolved = Column(Boolean, nullable=False, server_default=text("false"))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    customer = relationship("CustomerModel", back_populates="escalations")

    __table_args__ = (
        Index("ix_customer_escalations_org_customer", "organization_id", "customer_id"),
        Index("ix_customer_escalations_org_created", "organization_id", "created_at"),
    )


class CustomerAuditLogModel(Base):
    __tablename__ = "customer_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    changes = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    ip_address = Column(String, nullable=True)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_customer_audit_org_created", "organization_id", "created_at"),
        Index("ix_customer_audit_customer", "customer_id"),
        Index("ix_customer_audit_action", "organization_id", "action"),
    )


class TenantUsageEventModel(Base):
    """Granular metered usage events per organization."""

    __tablename__ = "tenant_usage_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    metric_code = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    billable_amount = Column(Float, nullable=True)
    unit_cost = Column(Float, nullable=True)
    billing_period = Column(String, nullable=True)
    currency = Column(String, nullable=False, server_default=text("'USD'"))
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    reference_type = Column(String, nullable=True)
    reference_id = Column(String, nullable=True)
    aggregation_key = Column(String, nullable=False)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("aggregation_key", name="uq_tenant_usage_events_agg_key"),
        Index("ix_tenant_usage_org_metric_recorded", "organization_id", "metric_code", "recorded_at"),
        Index("ix_tenant_usage_org_recorded", "organization_id", "recorded_at"),
    )


class TenantBillingQuotaModel(Base):
    """Per-tenant usage quota limits."""

    __tablename__ = "tenant_billing_quotas"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    metric_code = Column(String, nullable=False)
    period = Column(String, nullable=False, server_default=text("'monthly'"))
    limit_quantity = Column(Float, nullable=False)
    enforcement = Column(String, nullable=False, server_default=text("'soft'"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "metric_code",
            "period",
            name="uq_tenant_billing_quotas_org_metric_period",
        ),
        Index("ix_tenant_billing_quotas_org", "organization_id"),
    )


class TenantInvoiceModel(Base):
    """Tenant billing invoices for a usage period."""

    __tablename__ = "tenant_invoices"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    invoice_number = Column(String, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False, server_default=text("'draft'"))
    currency = Column(String, nullable=False, server_default=text("'USD'"))
    subtotal = Column(Float, nullable=False, server_default=text("0"))
    tax_amount = Column(Float, nullable=False, server_default=text("0"))
    total_amount = Column(Float, nullable=False, server_default=text("0"))
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    issued_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    line_items = relationship(
        "TenantInvoiceLineModel",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "invoice_number",
            name="uq_tenant_invoices_org_number",
        ),
        Index("ix_tenant_invoices_org_period", "organization_id", "period_start"),
    )


class TenantInvoiceLineModel(Base):
    """Line item on a tenant invoice."""

    __tablename__ = "tenant_invoice_lines"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(
        Integer,
        ForeignKey("tenant_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_code = Column(String, nullable=False)
    description = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    unit_price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )

    invoice = relationship("TenantInvoiceModel", back_populates="line_items")

    __table_args__ = (Index("ix_tenant_invoice_lines_invoice", "invoice_id"),)


class ConversationQualityEvaluationModel(Base):
    """Persisted automated conversation quality evaluation per workflow run."""

    __tablename__ = "conversation_quality_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=False)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    model_version = Column(String, nullable=False, server_default=text("'cq-v1'"))
    overall_score = Column(Float, nullable=False)
    dimension_scores = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    metrics = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    regression = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    flags = Column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )
    evaluated_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("workflow_run_id", name="uq_cq_evaluations_workflow_run"),
        Index("ix_cq_evaluations_org_evaluated", "organization_id", "evaluated_at"),
        Index("ix_cq_evaluations_org_workflow", "organization_id", "workflow_id"),
    )


class KenyanLearningSampleModel(Base):
    __tablename__ = "kenyan_learning_samples"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    target = Column(String, nullable=False)
    source = Column(String, nullable=False)
    run_reference_hash = Column(String, nullable=True)
    locale = Column(String, nullable=False, server_default=text("'mixed'"))
    payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    metadata_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_kenyan_learning_samples_org_target", "organization_id", "target"),
        Index("ix_kenyan_learning_samples_created", "organization_id", "created_at"),
    )


class KenyanLearningLabelTaskModel(Base):
    __tablename__ = "kenyan_learning_label_tasks"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    sample_id = Column(Integer, ForeignKey("kenyan_learning_samples.id"), nullable=False)
    target = Column(String, nullable=False)
    status = Column(String, nullable=False, server_default=text("'pending'"))
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    label_payload = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_kenyan_learning_labels_org_status", "organization_id", "status"),
    )


class KenyanLearningFeedbackModel(Base):
    __tablename__ = "kenyan_learning_feedback"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    feedback_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    sample_id = Column(Integer, ForeignKey("kenyan_learning_samples.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_kenyan_learning_feedback_org_type", "organization_id", "feedback_type"),
    )


class KenyanLearningTrainingRunModel(Base):
    __tablename__ = "kenyan_learning_training_runs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    status = Column(String, nullable=False, server_default=text("'queued'"))
    targets = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    artifacts = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_kenyan_learning_runs_org_created", "organization_id", "created_at"),
    )


class DurableOrchestrationModel(Base):
    __tablename__ = "durable_orchestrations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    orchestration_key = Column(String, nullable=False)
    definition_name = Column(String, nullable=False)
    status = Column(String, nullable=False, server_default=text("'pending'"))
    current_step = Column(String, nullable=False, server_default=text("''"))
    state = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    saga_stack = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    version = Column(Integer, nullable=False, server_default=text("1"))
    next_wake_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "orchestration_key",
            name="uq_durable_orchestrations_org_key",
        ),
        Index("ix_durable_orchestrations_org_status", "organization_id", "status"),
        Index("ix_durable_orchestrations_wake", "status", "next_wake_at"),
    )


class DurableOrchestrationEventModel(Base):
    __tablename__ = "durable_orchestration_events"

    id = Column(Integer, primary_key=True, index=True)
    orchestration_id = Column(
        Integer, ForeignKey("durable_orchestrations.id"), nullable=False
    )
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    idempotency_key = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index(
            "ix_durable_orch_events_orch_created",
            "orchestration_id",
            "created_at",
        ),
    )


class DurableScheduledTaskModel(Base):
    __tablename__ = "durable_scheduled_tasks"

    id = Column(Integer, primary_key=True, index=True)
    orchestration_id = Column(
        Integer, ForeignKey("durable_orchestrations.id"), nullable=False
    )
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    task_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    run_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False, server_default=text("'pending'"))
    attempt = Column(Integer, nullable=False, server_default=text("0"))
    max_attempts = Column(Integer, nullable=False, server_default=text("5"))
    last_error = Column(Text, nullable=True)
    idempotency_key = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_durable_scheduled_tasks_due", "status", "run_at"),
        Index("ix_durable_scheduled_tasks_orch", "orchestration_id", "status"),
    )


class PlatformEventModel(Base):
    __tablename__ = "platform_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(36), nullable=False, unique=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    event_type = Column(String, nullable=False)
    source = Column(String, nullable=False, server_default=text("''"))
    correlation_id = Column(String, nullable=True)
    payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    idempotency_key = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_platform_events_org_created", "organization_id", "created_at"),
        Index("ix_platform_events_org_type", "organization_id", "event_type"),
        Index("ix_platform_events_correlation", "correlation_id"),
    )


class CustomerTimelineEntryModel(Base):
    __tablename__ = "customer_timeline_entries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    phone_e164 = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("whatsapp_conversations.id"), nullable=True)
    transaction_id = Column(Integer, ForeignKey("mpesa_transactions.id"), nullable=True)
    correlation_id = Column(String, nullable=True)
    journey_state = Column(String, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    platform_event_id = Column(Integer, ForeignKey("platform_events.id"), nullable=True)
    idempotency_key = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index(
            "ix_customer_timeline_org_phone_occurred",
            "organization_id",
            "phone_e164",
            "occurred_at",
        ),
        Index(
            "ix_customer_timeline_org_customer_occurred",
            "organization_id",
            "customer_id",
            "occurred_at",
        ),
    )


class KenyanPhraseEntryModel(Base):
    """Admin-editable Kenyan / Sheng phrase dictionary."""

    __tablename__ = "kenyan_phrase_entries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    phrase = Column(String, nullable=False)
    meaning = Column(String, nullable=False)
    language = Column(String, nullable=False, server_default=text("'sheng'"))
    intent = Column(String, nullable=True)
    confidence = Column(Float, nullable=False, server_default=text("0.85"))
    context = Column(String, nullable=True)
    region = Column(String, nullable=False, server_default=text("'national'"))
    version = Column(String, nullable=False, server_default=text("'1'"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_kenyan_phrases_org_active", "organization_id", "is_active"),
        Index("ix_kenyan_phrases_phrase", "phrase"),
    )


class CustomerIdentityModel(Base):
    """External identifiers that resolve to a single CRM customer."""

    __tablename__ = "customer_identities"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind = Column(String, nullable=False)
    value = Column(String, nullable=False)
    is_primary = Column(Boolean, nullable=False, server_default=text("false"))
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "kind",
            "value",
            name="uq_customer_identities_org_kind_value",
        ),
        Index("ix_customer_identities_customer", "customer_id"),
        Index("ix_customer_identities_org_kind", "organization_id", "kind"),
    )


class CustomerCommunicationPreferenceModel(Base):
    """Kenya DPA / CAK-aligned contact and consent preferences."""

    __tablename__ = "customer_communication_preferences"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    preferred_channel = Column(String, nullable=False, server_default=text("'voice'"))
    preferred_locale = Column(String, nullable=False, server_default=text("'mixed'"))
    marketing_consent = Column(Boolean, nullable=False, server_default=text("false"))
    transactional_consent = Column(Boolean, nullable=False, server_default=text("true"))
    sms_opt_out = Column(Boolean, nullable=False, server_default=text("false"))
    whatsapp_opt_out = Column(Boolean, nullable=False, server_default=text("false"))
    voice_opt_out = Column(Boolean, nullable=False, server_default=text("false"))
    email_opt_out = Column(Boolean, nullable=False, server_default=text("false"))
    webchat_opt_out = Column(Boolean, nullable=False, server_default=text("false"))
    consent_source = Column(String, nullable=True)
    consent_recorded_at = Column(DateTime(timezone=True), nullable=True)
    legal_basis = Column(String, nullable=False, server_default=text("'contract'"))
    notes = Column(Text, nullable=True)
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_comm_prefs_org_customer", "organization_id", "customer_id"),
    )


class EngagementConversationModel(Base):
    """Unified customer conversation spanning voice, SMS, WhatsApp, and web chat."""

    __tablename__ = "engagement_conversations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    phone_e164 = Column(String, nullable=True)
    origin_channel = Column(String, nullable=False, server_default=text("'voice'"))
    last_channel = Column(String, nullable=False, server_default=text("'voice'"))
    status = Column(String, nullable=False, server_default=text("'open'"))
    correlation_id = Column(String, nullable=True)
    waiting_for_reply = Column(Boolean, nullable=False, server_default=text("false"))
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    messages = relationship(
        "EngagementMessageModel",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_engagement_conversations_org_customer",
            "organization_id",
            "customer_id",
            "status",
        ),
        Index("ix_engagement_conversations_org_phone", "organization_id", "phone_e164"),
        Index("ix_engagement_conversations_correlation", "correlation_id"),
    )


class EngagementMessageModel(Base):
    __tablename__ = "engagement_messages"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    conversation_id = Column(
        Integer,
        ForeignKey("engagement_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    channel = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    message_type = Column(String, nullable=False, server_default=text("'text'"))
    body = Column(Text, nullable=True)
    status = Column(String, nullable=False, server_default=text("'queued'"))
    provider_message_id = Column(String, nullable=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    transaction_id = Column(Integer, ForeignKey("mpesa_transactions.id"), nullable=True)
    consent_checked = Column(Boolean, nullable=False, server_default=text("true"))
    consent_allowed = Column(Boolean, nullable=False, server_default=text("true"))
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    conversation = relationship("EngagementConversationModel", back_populates="messages")

    __table_args__ = (
        Index(
            "ix_engagement_messages_conversation_created",
            "conversation_id",
            "created_at",
        ),
        Index("ix_engagement_messages_org_channel_created", "organization_id", "channel", "created_at"),
        Index("ix_engagement_messages_org_status", "organization_id", "status"),
    )


class EngagementFollowupRuleModel(Base):
    __tablename__ = "engagement_followup_rules"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    trigger_event = Column(String, nullable=False)
    action = Column(String, nullable=False)
    channel = Column(String, nullable=True)
    template_key = Column(String, nullable=True)
    delay_seconds = Column(Integer, nullable=False, server_default=text("0"))
    purpose = Column(String, nullable=False, server_default=text("'transactional'"))
    enabled = Column(Boolean, nullable=False, server_default=text("true"))
    metadata_json = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_engagement_followup_org_trigger", "organization_id", "trigger_event"),
    )


class BusinessKnowledgeEntryModel(Base):
    """Structured business knowledge retrieved at runtime, not stuffed into prompts."""

    __tablename__ = "business_knowledge_entries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    category = Column(String, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False, default="", server_default=text("''"))
    metadata_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    document_uuid = Column(String(36), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    source = Column(String(64), nullable=False, server_default=text("'business_admin'"))
    source_type = Column(String(64), nullable=False, server_default=text("'business_admin'"))
    source_reference = Column(String(512), nullable=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_changed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    freshness_score = Column(Float, nullable=False, server_default=text("1.0"))
    confidence = Column(Float, nullable=False, server_default=text("1.0"))
    status = Column(String(32), nullable=False, server_default=text("'verified'"))
    version = Column(Integer, nullable=False, server_default=text("1"))
    provenance_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    language = Column(String(16), nullable=True)
    location_id = Column(Integer, nullable=True)
    is_approved = Column(Boolean, nullable=False, server_default=text("true"))
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_biz_knowledge_org_category", "organization_id", "category"),
        Index("ix_biz_knowledge_org_active", "organization_id", "is_active"),
    )


class SecurityAuditEventModel(Base):
    """Append-only security audit records. Rows are never updated by application code."""

    __tablename__ = "security_audit_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    outcome = Column(String, nullable=False, server_default=text("'success'"))
    summary = Column(Text, nullable=True)
    metadata_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_security_audit_org_created", "organization_id", "created_at"),
        Index("ix_security_audit_action_created", "action", "created_at"),
    )


class OrganizationAuditLogModel(Base):
    """Append-only organization administrative audit log."""

    __tablename__ = "organization_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    metadata_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_org_audit_org_created", "organization_id", "created_at"),
        Index("ix_org_audit_org_action", "organization_id", "action"),
    )


class ConversationIntelligenceModel(Base):
    """Per-conversation labels for BI. Stores no raw phone, ID, or full transcript."""

    __tablename__ = "conversation_intelligence"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    category = Column(String, nullable=False)
    intent = Column(String, nullable=True)
    sentiment = Column(String, nullable=False, server_default=text("'neutral'"))
    outcome = Column(String, nullable=True)
    unresolved_issue = Column(String, nullable=True)
    requested_product = Column(String, nullable=True)
    next_action = Column(String, nullable=True)
    language = Column(String, nullable=True)
    county = Column(String, nullable=True)
    contained = Column(Boolean, nullable=False, server_default=text("true"))
    transferred = Column(Boolean, nullable=False, server_default=text("false"))
    first_contact_resolved = Column(
        Boolean, nullable=False, server_default=text("false")
    )
    redacted_excerpt = Column(Text, nullable=True)
    metadata_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_conv_intel_org_created", "organization_id", "created_at"),
        Index("ix_conv_intel_org_category", "organization_id", "category"),
        UniqueConstraint(
            "organization_id",
            "workflow_run_id",
            name="uq_conv_intel_org_run",
        ),
    )


class BusinessInsightModel(Base):
    """Generated, privacy-safe natural-language insights for an organization."""

    __tablename__ = "business_insights"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    kind = Column(String, nullable=False)
    headline = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    severity = Column(String, nullable=False, server_default=text("'info'"))
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_end = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_business_insights_org_created", "organization_id", "created_at"),
    )


class AgentEvalRunModel(Base):
    """One evaluation suite execution against a workflow version."""

    __tablename__ = "agent_eval_runs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    workflow_definition_id = Column(
        Integer, ForeignKey("workflow_definitions.id"), nullable=True
    )
    baseline_definition_id = Column(
        Integer, ForeignKey("workflow_definitions.id"), nullable=True
    )
    trigger = Column(String, nullable=False, server_default=text("'manual'"))
    status = Column(String, nullable=False, server_default=text("'completed'"))
    scenario_filter = Column(String, nullable=True)
    score_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    comparison_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    metrics_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_agent_eval_runs_org_created", "organization_id", "created_at"),
        Index("ix_agent_eval_runs_org_workflow", "organization_id", "workflow_id"),
    )


class AgentEvalResultModel(Base):
    """Per-scenario outcome for a suite run."""

    __tablename__ = "agent_eval_results"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    run_id = Column(
        Integer, ForeignKey("agent_eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    scenario_id = Column(String, nullable=False)
    category = Column(String, nullable=False)
    passed = Column(Boolean, nullable=False, server_default=text("false"))
    expected_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    actual_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    evaluation_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    transcript_json = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    tool_calls_json = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    workflow_path_json = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_agent_eval_results_run", "run_id"),
        Index(
            "ix_agent_eval_results_org_scenario",
            "organization_id",
            "scenario_id",
        ),
    )


class AgentEvalProductionSampleModel(Base):
    """Consent-gated, anonymized production turns for evaluation only."""

    __tablename__ = "agent_eval_production_samples"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    run_reference_hash = Column(String, nullable=True)
    consent_ok = Column(Boolean, nullable=False, server_default=text("false"))
    anonymized_turns = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    training_eligible = Column(Boolean, nullable=False, server_default=text("false"))
    governance_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index(
            "ix_agent_eval_prod_org_created",
            "organization_id",
            "created_at",
        ),
    )


class TwinProvenanceMixin:
    """Shared provenance/freshness columns for Digital Twin records."""

    source = Column(String(64), nullable=False, server_default=text("'business_admin'"))
    source_type = Column(String(64), nullable=False, server_default=text("'business_admin'"))
    source_reference = Column(String(512), nullable=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_changed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    freshness_score = Column(Float, nullable=False, server_default=text("1.0"))
    confidence = Column(Float, nullable=False, server_default=text("1.0"))
    status = Column(String(32), nullable=False, server_default=text("'verified'"))
    version = Column(Integer, nullable=False, server_default=text("1"))
    provenance_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )


class BusinessProfileModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    legal_name = Column(String(255), nullable=True)
    trading_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    industry = Column(String(64), nullable=True)
    sub_industry = Column(String(64), nullable=True)
    website = Column(String(512), nullable=True)
    email = Column(String(255), nullable=True)
    phones_json = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    counties_json = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    service_areas_json = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    social_channels_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    languages_json = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    hours_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    payment_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    operational_refs_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_business_profiles_org"),
        Index("ix_business_profiles_org", "organization_id"),
    )


class BusinessLocationModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_locations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    county = Column(String(64), nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(32), nullable=True)
    is_branch = Column(Boolean, nullable=False, server_default=text("true"))
    hours_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_locations_org", "organization_id"),)


class BusinessHoursModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    location_id = Column(Integer, ForeignKey("business_locations.id", ondelete="CASCADE"), nullable=True)
    weekday = Column(String(16), nullable=False)
    open_time = Column(String(8), nullable=True)
    close_time = Column(String(8), nullable=True)
    is_closed = Column(Boolean, nullable=False, server_default=text("false"))
    kind = Column(String(32), nullable=False, server_default=text("'regular'"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_hours_org", "organization_id"),)


class BusinessHolidayModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_holidays"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(128), nullable=False)
    holiday_date = Column(String(16), nullable=False)
    is_closed = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_holidays_org", "organization_id"),)


class BusinessOfferingModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_offerings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    kind = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price_amount = Column(Float, nullable=True)
    price_currency = Column(String(8), nullable=False, server_default=text("'KES'"))
    sku = Column(String(64), nullable=True)
    is_live_priced = Column(Boolean, nullable=False, server_default=text("false"))
    live_source_key = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_offerings_org_kind", "organization_id", "kind"),)


class BusinessPolicyModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_policies"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False, default="", server_default=text("''"))
    policy_type = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_policies_org", "organization_id"),)


class BusinessFaqModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_faqs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    language = Column(String(16), nullable=False, server_default=text("'en'"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_faqs_org", "organization_id"),)


class BusinessContactModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_contacts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    role = Column(String(128), nullable=True)
    department = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True)
    is_escalation = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_contacts_org", "organization_id"),)


class BusinessAnnouncementModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_announcements"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    priority = Column(Integer, nullable=False, server_default=text("0"))
    location_id = Column(Integer, ForeignKey("business_locations.id", ondelete="SET NULL"), nullable=True)
    languages_json = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    affected_services_json = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    announcement_status = Column(String(32), nullable=False, server_default=text("'active'"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_announcements_org", "organization_id"),)


class BusinessDataSourceModel(Base):
    __tablename__ = "business_data_sources"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    provider_kind = Column(String(64), nullable=False)
    adapter_key = Column(String(64), nullable=False)
    display_name = Column(String(255), nullable=False)
    schedule = Column(String(32), nullable=False, server_default=text("'daily'"))
    is_live = Column(Boolean, nullable=False, server_default=text("true"))
    webhook_secret = Column(String(128), nullable=True)
    credentials_json = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    allowlisted_hosts_json = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    lifecycle_state = Column(String(32), nullable=False, server_default=text("'discovered'"))
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_rate = Column(Float, nullable=False, server_default=text("0"))
    auth_status = Column(String(32), nullable=False, server_default=text("'unknown'"))
    records_synced = Column(Integer, nullable=False, server_default=text("0"))
    config_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    status = Column(String(32), nullable=False, server_default=text("'active'"))
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_data_sources_org", "organization_id"),)


class BusinessDataSnapshotModel(Base):
    __tablename__ = "business_data_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    source_id = Column(
        Integer, ForeignKey("business_data_sources.id", ondelete="CASCADE"), nullable=False
    )
    payload_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    record_count = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_business_snapshots_org_source", "organization_id", "source_id"),)


class BusinessDataChangeModel(Base):
    __tablename__ = "business_data_changes"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    field_path = Column(String(255), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    source = Column(String(64), nullable=False)
    source_id = Column(Integer, nullable=True)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    confidence = Column(Float, nullable=False, server_default=text("1.0"))
    risk_level = Column(String(16), nullable=False, server_default=text("'medium'"))
    status = Column(String(32), nullable=False, server_default=text("'detected'"))
    category = Column(String(32), nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))

    __table_args__ = (Index("ix_business_changes_org_status", "organization_id", "status"),)


class BusinessConflictModel(Base):
    __tablename__ = "business_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    field_path = Column(String(255), nullable=False)
    source_a = Column(String(64), nullable=False)
    value_a = Column(Text, nullable=True)
    source_b = Column(String(64), nullable=False)
    value_b = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, server_default=text("1.0"))
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    resolution_status = Column(String(32), nullable=False, server_default=text("'open'"))
    resolved_source = Column(String(64), nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (Index("ix_business_conflicts_org", "organization_id", "resolution_status"),)


class BusinessSyncJobModel(Base):
    __tablename__ = "business_sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    source_id = Column(
        Integer, ForeignKey("business_data_sources.id", ondelete="CASCADE"), nullable=False
    )
    schedule = Column(String(32), nullable=False, server_default=text("'daily'"))
    enabled = Column(Boolean, nullable=False, server_default=text("true"))
    lock_until = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_business_sync_jobs_next", "enabled", "next_run_at"),)


class BusinessSyncRunModel(Base):
    __tablename__ = "business_sync_runs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    job_id = Column(Integer, ForeignKey("business_sync_jobs.id", ondelete="SET NULL"), nullable=True)
    source_id = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    ended_at = Column(DateTime(timezone=True), nullable=True)
    records_discovered = Column(Integer, nullable=False, server_default=text("0"))
    records_changed = Column(Integer, nullable=False, server_default=text("0"))
    records_failed = Column(Integer, nullable=False, server_default=text("0"))
    conflicts = Column(Integer, nullable=False, server_default=text("0"))
    duration_ms = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, server_default=text("'running'"))
    error_summary = Column(Text, nullable=True)
    correlation_id = Column(String(64), nullable=True)

    __table_args__ = (Index("ix_business_sync_runs_org", "organization_id", "started_at"),)


class BusinessSyncErrorModel(Base):
    __tablename__ = "business_sync_errors"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    run_id = Column(Integer, ForeignKey("business_sync_runs.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    detail_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class BusinessApprovalModel(Base):
    __tablename__ = "business_approvals"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    change_id = Column(
        Integer, ForeignKey("business_data_changes.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decision = Column(String(16), nullable=False, server_default=text("'pending'"))
    reason = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    session_id = Column(String(128), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_business_approvals_org", "organization_id", "decision"),)


class BusinessEventModel(Base):
    __tablename__ = "business_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    event_type = Column(String(64), nullable=False)
    source_id = Column(Integer, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    processed = Column(Boolean, nullable=False, server_default=text("false"))
    correlation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_business_events_org_type", "organization_id", "event_type"),)


class BusinessAlertModel(Base):
    __tablename__ = "business_alerts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    code = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    severity = Column(String(16), nullable=False, server_default=text("'warning'"))
    action_url = Column(String(255), nullable=True)
    is_open = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_business_alerts_org_open", "organization_id", "is_open"),)


class BusinessFieldVersionModel(Base):
    __tablename__ = "business_field_versions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer, nullable=False)
    field_path = Column(String(255), nullable=False)
    value = Column(Text, nullable=True)
    version = Column(Integer, nullable=False)
    source = Column(String(64), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index(
            "ix_business_field_versions_entity",
            "organization_id",
            "entity_type",
            "entity_id",
            "field_path",
        ),
    )


class BusinessSourceAuthorityModel(Base):
    __tablename__ = "business_source_authority"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    data_type = Column(String(64), nullable=False)
    ranked_sources_json = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "data_type", name="uq_business_source_authority"),
    )


class BusinessInterviewSessionModel(Base):
    __tablename__ = "business_interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    transcript = Column(Text, nullable=False, default="", server_default=text("''"))
    extracted_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    status = Column(String(32), nullable=False, server_default=text("'draft'"))
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_interview_org", "organization_id"),)


class BusinessAgentTraceModel(Base):
    __tablename__ = "business_agent_traces"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    question = Column(Text, nullable=False)
    intent = Column(String(64), nullable=True)
    source_selected = Column(String(64), nullable=True)
    authority = Column(String(32), nullable=True)
    freshness = Column(Float, nullable=True)
    tool_used = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    result_summary = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    workflow_run_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_business_traces_org", "organization_id", "created_at"),)


class BusinessUnansweredQuestionModel(Base):
    __tablename__ = "business_unanswered_questions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    question_redacted = Column(Text, nullable=False)
    intent = Column(String(64), nullable=True)
    missing_field = Column(String(64), nullable=True)
    hit_count = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_business_unanswered_org", "organization_id", "hit_count"),
    )


class BusinessOverrideModel(Base):
    __tablename__ = "business_overrides"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    field_path = Column(String(255), nullable=False)
    source_value = Column(Text, nullable=True)
    override_value = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_business_overrides_org", "organization_id", "field_path"),)


class BusinessPromotionModel(TwinProvenanceMixin, Base):
    __tablename__ = "business_promotions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    discount = Column(String(64), nullable=True)
    applicable = Column(String(255), nullable=True)
    location_id = Column(Integer, ForeignKey("business_locations.id", ondelete="SET NULL"), nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    eligibility = Column(Text, nullable=True)
    promotion_status = Column(String(32), nullable=False, server_default=text("'active'"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_business_promotions_org", "organization_id"),)


class ProductAnalyticsEventModel(Base):
    """Product funnel events. No phone numbers or transcripts."""

    __tablename__ = "product_analytics_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    event_name = Column(String, nullable=False)
    properties = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index(
            "ix_product_analytics_org_event",
            "organization_id",
            "event_name",
            "created_at",
        ),
    )
