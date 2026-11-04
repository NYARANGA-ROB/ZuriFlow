"""add security audit events

Revision ID: u0v1w2x3y4z5
Revises: t9u0v1w2x3y4
Create Date: 2026-08-24 05:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u0v1w2x3y4z5"
down_revision: Union[str, None] = "t9u0v1w2x3y4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False, server_default="success"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_security_audit_org_created",
        "security_audit_events",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_security_audit_action_created",
        "security_audit_events",
        ["action", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_audit_action_created", table_name="security_audit_events")
    op.drop_index("ix_security_audit_org_created", table_name="security_audit_events")
    op.drop_table("security_audit_events")
