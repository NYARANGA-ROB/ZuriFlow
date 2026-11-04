"""add whatsapp conversations and messages

Revision ID: b8a7c3d4e5f6
Revises: 91cc6ba3e1c7
Create Date: 2026-06-23 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8a7c3d4e5f6"
down_revision: Union[str, None] = "91cc6ba3e1c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("phone_e164", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "escalated",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "phone_e164",
            "provider",
            name="uq_whatsapp_conversations_org_phone_provider",
        ),
    )
    op.create_index(
        "ix_whatsapp_conversations_org_updated",
        "whatsapp_conversations",
        ["organization_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_whatsapp_conversations_id"),
        "whatsapp_conversations",
        ["id"],
        unique=False,
    )

    op.create_table(
        "whatsapp_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("template_name", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["whatsapp_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_whatsapp_messages_conversation_created",
        "whatsapp_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_whatsapp_messages_id"),
        "whatsapp_messages",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_whatsapp_messages_id"), table_name="whatsapp_messages")
    op.drop_index(
        "ix_whatsapp_messages_conversation_created",
        table_name="whatsapp_messages",
    )
    op.drop_table("whatsapp_messages")
    op.drop_index(op.f("ix_whatsapp_conversations_id"), table_name="whatsapp_conversations")
    op.drop_index(
        "ix_whatsapp_conversations_org_updated",
        table_name="whatsapp_conversations",
    )
    op.drop_table("whatsapp_conversations")
