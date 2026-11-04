"""add conversation intelligence and business insight tables

Revision ID: s8t9u0v1w2x3
Revises: r7s8t9u0v1w2
Create Date: 2026-08-24 03:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s8t9u0v1w2x3"
down_revision: Union[str, None] = "r7s8t9u0v1w2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_intelligence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("sentiment", sa.String(), server_default=sa.text("'neutral'"), nullable=False),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("unresolved_issue", sa.String(), nullable=True),
        sa.Column("requested_product", sa.String(), nullable=True),
        sa.Column("next_action", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("county", sa.String(), nullable=True),
        sa.Column("contained", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("transferred", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "first_contact_resolved",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("redacted_excerpt", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "workflow_run_id", name="uq_conv_intel_org_run"
        ),
    )
    op.create_index(
        "ix_conv_intel_org_created",
        "conversation_intelligence",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_conv_intel_org_category",
        "conversation_intelligence",
        ["organization_id", "category"],
    )

    op.create_table(
        "business_insights",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("headline", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(), server_default=sa.text("'info'"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_business_insights_org_created",
        "business_insights",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_business_insights_org_created", table_name="business_insights")
    op.drop_table("business_insights")
    op.drop_index("ix_conv_intel_org_category", table_name="conversation_intelligence")
    op.drop_index("ix_conv_intel_org_created", table_name="conversation_intelligence")
    op.drop_table("conversation_intelligence")
