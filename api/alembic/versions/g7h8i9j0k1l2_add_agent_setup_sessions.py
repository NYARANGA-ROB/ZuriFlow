"""add agent setup sessions for self-serve wizard

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-24 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_setup_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_uuid", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), server_default="industry", nullable=False),
        sa.Column("config", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=True),
        sa.Column("phone_number_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["phone_number_id"], ["telephony_phone_numbers.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_uuid"),
    )
    op.create_index(
        "ix_agent_setup_sessions_org_user",
        "agent_setup_sessions",
        ["organization_id", "user_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_setup_sessions_state",
        "agent_setup_sessions",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_setup_sessions_session_uuid"),
        "agent_setup_sessions",
        ["session_uuid"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_setup_sessions_session_uuid"), table_name="agent_setup_sessions")
    op.drop_index("ix_agent_setup_sessions_state", table_name="agent_setup_sessions")
    op.drop_index("ix_agent_setup_sessions_org_user", table_name="agent_setup_sessions")
    op.drop_table("agent_setup_sessions")
