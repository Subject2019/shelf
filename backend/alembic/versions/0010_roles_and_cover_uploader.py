"""三级角色（admin/editor/listener）与封面上传者记录

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 旧的两档模型里 user = 只能收听，映射到新的 listener 语义
    op.execute("UPDATE users SET role = 'listener' WHERE role = 'user'")
    # 记录手工封面的上传者：扫描抽取的封面为 NULL
    # 用 add_column 而不是 batch_alter_table —— 重建 books 表会连带丢掉
    # books_fts 的三个同步触发器（external content 表）
    op.add_column("books", sa.Column("cover_uploaded_by", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "cover_uploaded_by")
    op.execute("UPDATE users SET role = 'user' WHERE role IN ('editor', 'listener')")
