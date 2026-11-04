"""add customer phone_original for Kenyan format preservation

Revision ID: o4p5q6r7s8t9
Revises: n3o4p5q6r7s8
Create Date: 2026-08-23 19:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o4p5q6r7s8t9"
down_revision: Union[str, None] = "n3o4p5q6r7s8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("phone_original", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "phone_original")
