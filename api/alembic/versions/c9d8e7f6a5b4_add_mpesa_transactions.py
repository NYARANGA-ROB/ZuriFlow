"""add mpesa daraja transaction tables

Revision ID: c9d8e7f6a5b4
Revises: b8a7c3d4e5f6
Create Date: 2026-06-23 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d8e7f6a5b4"
down_revision: Union[str, None] = "b8a7c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mpesa_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("phone_e164", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), server_default=sa.text("'KES'"), nullable=False),
        sa.Column("account_reference", sa.String(), nullable=False),
        sa.Column("transaction_desc", sa.String(), nullable=False),
        sa.Column("merchant_request_id", sa.String(), nullable=True),
        sa.Column("checkout_request_id", sa.String(), nullable=True),
        sa.Column("mpesa_receipt_number", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("result_code", sa.Integer(), nullable=True),
        sa.Column("result_desc", sa.String(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("callback_payload", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("checkout_request_id"),
    )
    op.create_index(
        "ix_mpesa_transactions_org_status",
        "mpesa_transactions",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_mpesa_transactions_org_created",
        "mpesa_transactions",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_mpesa_transactions_receipt",
        "mpesa_transactions",
        ["mpesa_receipt_number"],
        unique=False,
        postgresql_where=sa.text("mpesa_receipt_number IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_mpesa_transactions_id"),
        "mpesa_transactions",
        ["id"],
        unique=False,
    )

    op.create_table(
        "mpesa_transaction_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["mpesa_transactions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mpesa_transaction_events_tx_created",
        "mpesa_transaction_events",
        ["transaction_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mpesa_transaction_events_id"),
        "mpesa_transaction_events",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mpesa_transaction_events_id"), table_name="mpesa_transaction_events")
    op.drop_index(
        "ix_mpesa_transaction_events_tx_created",
        table_name="mpesa_transaction_events",
    )
    op.drop_table("mpesa_transaction_events")
    op.drop_index(op.f("ix_mpesa_transactions_id"), table_name="mpesa_transactions")
    op.drop_index("ix_mpesa_transactions_receipt", table_name="mpesa_transactions")
    op.drop_index("ix_mpesa_transactions_org_created", table_name="mpesa_transactions")
    op.drop_index("ix_mpesa_transactions_org_status", table_name="mpesa_transactions")
    op.drop_table("mpesa_transactions")
