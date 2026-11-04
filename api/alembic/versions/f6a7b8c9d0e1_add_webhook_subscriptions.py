"""add webhook subscriptions for public API platform

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-24 08:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("subscription_uuid", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("secret", sa.String(), nullable=False),
        sa.Column("events", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_uuid"),
    )
    op.create_index(
        "ix_webhook_subscriptions_org_id",
        "webhook_subscriptions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_subscriptions_active",
        "webhook_subscriptions",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_subscriptions_active", table_name="webhook_subscriptions")
    op.drop_index("ix_webhook_subscriptions_org_id", table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
