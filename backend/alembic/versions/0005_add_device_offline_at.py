"""add devices.offline_at

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25 10:10:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 客户端显式上报「我离开了」时写入；任何后续请求都会清空
    op.add_column("devices", sa.Column("offline_at", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "offline_at")
