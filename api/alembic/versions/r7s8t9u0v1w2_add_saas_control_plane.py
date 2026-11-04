"""add saas control plane tables and workflow changelog

Revision ID: r7s8t9u0v1w2
Revises: q6r7s8t9u0v1
Create Date: 2026-08-24 02:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r7s8t9u0v1w2"
down_revision: Union[str, None] = "q6r7s8t9u0v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflow_definitions", sa.Column("changelog", sa.Text(), nullable=True))
    op.add_column(
        "workflow_definitions",
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "workflow_definitions",
        sa.Column("published_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_definitions_created_by_user",
        "workflow_definitions",
        "users",
        ["created_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_workflow_definitions_published_by_user",
        "workflow_definitions",
        "users",
        ["published_by_user_id"],
        ["id"],
    )

    op.create_table(
        "business_knowledge_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("document_uuid", sa.String(length=36), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_biz_knowledge_org_category",
        "business_knowledge_entries",
        ["organization_id", "category"],
    )
    op.create_index(
        "ix_biz_knowledge_org_active",
        "business_knowledge_entries",
        ["organization_id", "is_active"],
    )

    op.create_table(
        "organization_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_audit_org_created",
        "organization_audit_logs",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_org_audit_org_action",
        "organization_audit_logs",
        ["organization_id", "action"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_audit_org_action", table_name="organization_audit_logs")
    op.drop_index("ix_org_audit_org_created", table_name="organization_audit_logs")
    op.drop_table("organization_audit_logs")
    op.drop_index("ix_biz_knowledge_org_active", table_name="business_knowledge_entries")
    op.drop_index(
        "ix_biz_knowledge_org_category", table_name="business_knowledge_entries"
    )
    op.drop_table("business_knowledge_entries")
    op.drop_constraint(
        "fk_workflow_definitions_published_by_user",
        "workflow_definitions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_workflow_definitions_created_by_user",
        "workflow_definitions",
        type_="foreignkey",
    )
    op.drop_column("workflow_definitions", "published_by_user_id")
    op.drop_column("workflow_definitions", "created_by_user_id")
    op.drop_column("workflow_definitions", "changelog")
