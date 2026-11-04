"""add organization members RBAC

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-23 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.String(),
            server_default=sa.text("'viewer'"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "user_id", name="_organization_member_uc"
        ),
    )
    op.create_index(
        "ix_organization_members_org_id",
        "organization_members",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_members_user_id",
        "organization_members",
        ["user_id"],
        unique=False,
    )

    # Backfill from organization_users: first user per org becomes owner, rest viewer.
    op.execute(
        sa.text(
            """
            INSERT INTO organization_members (organization_id, user_id, role)
            SELECT ou.organization_id,
                   ou.user_id,
                   CASE
                       WHEN ou.user_id = (
                           SELECT MIN(ou2.user_id)
                           FROM organization_users ou2
                           WHERE ou2.organization_id = ou.organization_id
                       ) THEN 'owner'
                       ELSE 'viewer'
                   END
            FROM organization_users ou
            ON CONFLICT (organization_id, user_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_organization_members_user_id", table_name="organization_members")
    op.drop_index("ix_organization_members_org_id", table_name="organization_members")
    op.drop_table("organization_members")
