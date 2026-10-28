"""书籍增加片头/片尾跳过时长

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column("intro_sec", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "books",
        sa.Column("outro_sec", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("books", "outro_sec")
    op.drop_column("books", "intro_sec")
