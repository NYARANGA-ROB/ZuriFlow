"""add customer CRM tables

Revision ID: d4e5f6a7b8c9
Revises: c9d8e7f6a5b4
Create Date: 2026-06-23 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c9d8e7f6a5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("customer_uuid", sa.String(), nullable=False),
        sa.Column("external_crm_id", sa.String(), nullable=True),
        sa.Column("phone_e164", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column(
            "preferred_locale",
            sa.String(),
            server_default=sa.text("'mixed'"),
            nullable=False,
        ),
        sa.Column(
            "secondary_locales",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_uuid"),
        sa.UniqueConstraint("organization_id", "phone_e164", name="uq_customers_org_phone"),
    )
    op.create_index("ix_customers_org_external_crm", "customers", ["organization_id", "external_crm_id"])
    op.create_index("ix_customers_org_name", "customers", ["organization_id", "full_name"])
    op.create_index(op.f("ix_customers_id"), "customers", ["id"], unique=False)

    op.create_table(
        "customer_debt_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("account_reference", sa.String(), nullable=False),
        sa.Column("outstanding_balance", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("currency", sa.String(), server_default=sa.text("'KES'"), nullable=False),
        sa.Column("days_past_due", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("minimum_settlement", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "account_reference",
            name="uq_customer_debt_org_account_ref",
        ),
    )
    op.create_index("ix_customer_debt_org_status", "customer_debt_accounts", ["organization_id", "status"])
    op.create_index("ix_customer_debt_customer", "customer_debt_accounts", ["customer_id"])
    op.create_index(op.f("ix_customer_debt_accounts_id"), "customer_debt_accounts", ["id"], unique=False)

    op.create_table(
        "customer_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("debt_account_id", sa.Integer(), nullable=True),
        sa.Column("mpesa_transaction_id", sa.Integer(), nullable=True),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), server_default=sa.text("'KES'"), nullable=False),
        sa.Column("payment_method", sa.String(), server_default=sa.text("'mpesa'"), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("receipt_reference", sa.String(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["debt_account_id"], ["customer_debt_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mpesa_transaction_id"], ["mpesa_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_payments_org_customer", "customer_payments", ["organization_id", "customer_id"])
    op.create_index("ix_customer_payments_org_paid_at", "customer_payments", ["organization_id", "paid_at"])
    op.create_index(op.f("ix_customer_payments_id"), "customer_payments", ["id"], unique=False)

    op.create_table(
        "customer_call_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("call_type", sa.String(), server_default=sa.text("'outbound'"), nullable=False),
        sa.Column("phone_e164", sa.String(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("disposition", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("language", sa.String(), server_default=sa.text("'mixed'"), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_calls_org_customer", "customer_call_history", ["organization_id", "customer_id"])
    op.create_index("ix_customer_calls_workflow_run", "customer_call_history", ["workflow_run_id"])
    op.create_index(op.f("ix_customer_call_history_id"), "customer_call_history", ["id"], unique=False)

    op.create_table(
        "customer_escalation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("risk_level", sa.String(), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("queue_name", sa.String(), nullable=True),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_customer_escalations_org_customer",
        "customer_escalation_history",
        ["organization_id", "customer_id"],
    )
    op.create_index(
        "ix_customer_escalations_org_created",
        "customer_escalation_history",
        ["organization_id", "created_at"],
    )
    op.create_index(
        op.f("ix_customer_escalation_history_id"),
        "customer_escalation_history",
        ["id"],
        unique=False,
    )

    op.create_table(
        "customer_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_audit_org_created", "customer_audit_logs", ["organization_id", "created_at"])
    op.create_index("ix_customer_audit_customer", "customer_audit_logs", ["customer_id"])
    op.create_index("ix_customer_audit_action", "customer_audit_logs", ["organization_id", "action"])
    op.create_index(op.f("ix_customer_audit_logs_id"), "customer_audit_logs", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_customer_audit_logs_id"), table_name="customer_audit_logs")
    op.drop_index("ix_customer_audit_action", table_name="customer_audit_logs")
    op.drop_index("ix_customer_audit_customer", table_name="customer_audit_logs")
    op.drop_index("ix_customer_audit_org_created", table_name="customer_audit_logs")
    op.drop_table("customer_audit_logs")

    op.drop_index(op.f("ix_customer_escalation_history_id"), table_name="customer_escalation_history")
    op.drop_index("ix_customer_escalations_org_created", table_name="customer_escalation_history")
    op.drop_index("ix_customer_escalations_org_customer", table_name="customer_escalation_history")
    op.drop_table("customer_escalation_history")

    op.drop_index(op.f("ix_customer_call_history_id"), table_name="customer_call_history")
    op.drop_index("ix_customer_calls_workflow_run", table_name="customer_call_history")
    op.drop_index("ix_customer_calls_org_customer", table_name="customer_call_history")
    op.drop_table("customer_call_history")

    op.drop_index(op.f("ix_customer_payments_id"), table_name="customer_payments")
    op.drop_index("ix_customer_payments_org_paid_at", table_name="customer_payments")
    op.drop_index("ix_customer_payments_org_customer", table_name="customer_payments")
    op.drop_table("customer_payments")

    op.drop_index(op.f("ix_customer_debt_accounts_id"), table_name="customer_debt_accounts")
    op.drop_index("ix_customer_debt_customer", table_name="customer_debt_accounts")
    op.drop_index("ix_customer_debt_org_status", table_name="customer_debt_accounts")
    op.drop_table("customer_debt_accounts")

    op.drop_index(op.f("ix_customers_id"), table_name="customers")
    op.drop_index("ix_customers_org_name", table_name="customers")
    op.drop_index("ix_customers_org_external_crm", table_name="customers")
    op.drop_table("customers")
