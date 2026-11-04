"""add kenyan phrase catalog

Revision ID: p5q6r7s8t9u0
Revises: o4p5q6r7s8t9
Create Date: 2026-08-23 19:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p5q6r7s8t9u0"
down_revision: Union[str, None] = "o4p5q6r7s8t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kenyan_phrase_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("phrase", sa.String(), nullable=False),
        sa.Column("meaning", sa.String(), nullable=False),
        sa.Column("language", sa.String(), server_default=sa.text("'sheng'"), nullable=False),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.85"), nullable=False),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("region", sa.String(), server_default=sa.text("'national'"), nullable=False),
        sa.Column("version", sa.String(), server_default=sa.text("'1'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kenyan_phrases_org_active",
        "kenyan_phrase_entries",
        ["organization_id", "is_active"],
    )
    op.create_index("ix_kenyan_phrases_phrase", "kenyan_phrase_entries", ["phrase"])


def downgrade() -> None:
    op.drop_index("ix_kenyan_phrases_phrase", table_name="kenyan_phrase_entries")
    op.drop_index("ix_kenyan_phrases_org_active", table_name="kenyan_phrase_entries")
    op.drop_table("kenyan_phrase_entries")
