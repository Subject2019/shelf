"""进度检查点表：同账号同书保留最近 5 个明显不同的位置

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "progress_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("position_sec", sa.Float(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_progress_history_user_book",
        "progress_history",
        ["user_id", "book_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_progress_history_user_book", table_name="progress_history")
    op.drop_table("progress_history")
