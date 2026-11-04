"""add cancelled campaign state

Revision ID: t9u0v1w2x3y4
Revises: s8t9u0v1w2x3
Create Date: 2026-08-24 04:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "t9u0v1w2x3y4"
down_revision: Union[str, None] = "s8t9u0v1w2x3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE campaign_state ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value safely.
    pass
