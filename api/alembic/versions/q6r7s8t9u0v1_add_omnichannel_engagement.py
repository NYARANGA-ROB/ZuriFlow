"""add omnichannel engagement tables

Revision ID: q6r7s8t9u0v1
Revises: p5q6r7s8t9u0
Create Date: 2026-08-24 02:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q6r7s8t9u0v1"
down_revision: Union[str, None] = "p5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "kind",
            "value",
            name="uq_customer_identities_org_kind_value",
        ),
    )
    op.create_index("ix_customer_identities_customer", "customer_identities", ["customer_id"])
    op.create_index(
        "ix_customer_identities_org_kind",
        "customer_identities",
        ["organization_id", "kind"],
    )

    op.create_table(
        "customer_communication_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("preferred_channel", sa.String(), server_default=sa.text("'voice'"), nullable=False),
        sa.Column("preferred_locale", sa.String(), server_default=sa.text("'mixed'"), nullable=False),
        sa.Column("marketing_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("transactional_consent", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sms_opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("whatsapp_opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("voice_opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("email_opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("webchat_opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("consent_source", sa.String(), nullable=True),
        sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_basis", sa.String(), server_default=sa.text("'contract'"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id"),
    )
    op.create_index(
        "ix_comm_prefs_org_customer",
        "customer_communication_preferences",
        ["organization_id", "customer_id"],
    )

    op.create_table(
        "engagement_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("phone_e164", sa.String(), nullable=True),
        sa.Column("origin_channel", sa.String(), server_default=sa.text("'voice'"), nullable=False),
        sa.Column("last_channel", sa.String(), server_default=sa.text("'voice'"), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'open'"), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("waiting_for_reply", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_engagement_conversations_org_customer",
        "engagement_conversations",
        ["organization_id", "customer_id", "status"],
    )
    op.create_index(
        "ix_engagement_conversations_org_phone",
        "engagement_conversations",
        ["organization_id", "phone_e164"],
    )
    op.create_index(
        "ix_engagement_conversations_correlation",
        "engagement_conversations",
        ["correlation_id"],
    )

    op.create_table(
        "engagement_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), server_default=sa.text("'text'"), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("consent_checked", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("consent_allowed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["engagement_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["mpesa_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_engagement_messages_conversation_created",
        "engagement_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_engagement_messages_org_channel_created",
        "engagement_messages",
        ["organization_id", "channel", "created_at"],
    )
    op.create_index(
        "ix_engagement_messages_org_status",
        "engagement_messages",
        ["organization_id", "status"],
    )

    op.create_table(
        "engagement_followup_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trigger_event", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("template_key", sa.String(), nullable=True),
        sa.Column("delay_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("purpose", sa.String(), server_default=sa.text("'transactional'"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_engagement_followup_org_trigger",
        "engagement_followup_rules",
        ["organization_id", "trigger_event"],
    )


def downgrade() -> None:
    op.drop_table("engagement_followup_rules")
    op.drop_table("engagement_messages")
    op.drop_table("engagement_conversations")
    op.drop_table("customer_communication_preferences")
    op.drop_table("customer_identities")
