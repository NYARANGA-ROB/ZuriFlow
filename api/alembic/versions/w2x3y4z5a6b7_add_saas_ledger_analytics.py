"""add saas ledger columns and product analytics

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2026-08-24 07:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w2x3y4z5a6b7"
down_revision: Union[str, None] = "v1w2x3y4z5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenant_usage_events", sa.Column("unit_cost", sa.Float(), nullable=True))
    op.add_column("tenant_usage_events", sa.Column("billing_period", sa.String(), nullable=True))
    op.create_index(
        "ix_tenant_usage_org_period",
        "tenant_usage_events",
        ["organization_id", "billing_period"],
    )
    op.create_table(
        "product_analytics_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column(
            "properties",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_product_analytics_org_event",
        "product_analytics_events",
        ["organization_id", "event_name", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_analytics_org_event", table_name="product_analytics_events")
    op.drop_table("product_analytics_events")
    op.drop_index("ix_tenant_usage_org_period", table_name="tenant_usage_events")
    op.drop_column("tenant_usage_events", "billing_period")
    op.drop_column("tenant_usage_events", "unit_cost")
