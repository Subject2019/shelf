"""书籍隐藏：管理员可在书架中隐藏

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 用 add_column 而不是 batch_alter_table：重建 books 会连带丢掉 books_fts 的同步触发器
    op.add_column(
        "books",
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("books", "hidden")
