"""免密听众：只允许 listener 角色使用用户名直接登录。

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "passwordless",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "passwordless")
