"""add tenant usage billing tables

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-06-24 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("billable_amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(), server_default=sa.text("'USD'"), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("reference_type", sa.String(), nullable=True),
        sa.Column("reference_id", sa.String(), nullable=True),
        sa.Column("aggregation_key", sa.String(), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aggregation_key", name="uq_tenant_usage_events_agg_key"),
    )
    op.create_index(
        "ix_tenant_usage_org_metric_recorded",
        "tenant_usage_events",
        ["organization_id", "metric_code", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_tenant_usage_org_recorded",
        "tenant_usage_events",
        ["organization_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_usage_events_id"),
        "tenant_usage_events",
        ["id"],
        unique=False,
    )

    op.create_table(
        "tenant_billing_quotas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(), nullable=False),
        sa.Column("period", sa.String(), server_default=sa.text("'monthly'"), nullable=False),
        sa.Column("limit_quantity", sa.Float(), nullable=False),
        sa.Column("enforcement", sa.String(), server_default=sa.text("'soft'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "metric_code",
            "period",
            name="uq_tenant_billing_quotas_org_metric_period",
        ),
    )
    op.create_index(
        "ix_tenant_billing_quotas_org",
        "tenant_billing_quotas",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "tenant_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("currency", sa.String(), server_default=sa.text("'USD'"), nullable=False),
        sa.Column("subtotal", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("tax_amount", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_amount", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "invoice_number",
            name="uq_tenant_invoices_org_number",
        ),
    )
    op.create_index(
        "ix_tenant_invoices_org_period",
        "tenant_invoices",
        ["organization_id", "period_start"],
        unique=False,
    )

    op.create_table(
        "tenant_invoice_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["tenant_invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tenant_invoice_lines_invoice",
        "tenant_invoice_lines",
        ["invoice_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_invoice_lines_invoice", table_name="tenant_invoice_lines")
    op.drop_table("tenant_invoice_lines")
    op.drop_index("ix_tenant_invoices_org_period", table_name="tenant_invoices")
    op.drop_table("tenant_invoices")
    op.drop_index("ix_tenant_billing_quotas_org", table_name="tenant_billing_quotas")
    op.drop_table("tenant_billing_quotas")
    op.drop_index(op.f("ix_tenant_usage_events_id"), table_name="tenant_usage_events")
    op.drop_index("ix_tenant_usage_org_recorded", table_name="tenant_usage_events")
    op.drop_index("ix_tenant_usage_org_metric_recorded", table_name="tenant_usage_events")
    op.drop_table("tenant_usage_events")
