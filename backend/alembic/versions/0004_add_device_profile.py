"""add device profile fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-25 01:20:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 让「我的设备」能显示到浏览器/系统/机型这一级
    op.add_column("devices", sa.Column("user_agent", sa.Text(), nullable=True))
    op.add_column("devices", sa.Column("os", sa.Text(), nullable=True))
    op.add_column("devices", sa.Column("form_factor", sa.Text(), nullable=True))
    op.add_column("devices", sa.Column("screen", sa.Text(), nullable=True))
    op.add_column("devices", sa.Column("created_at", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "created_at")
    op.drop_column("devices", "screen")
    op.drop_column("devices", "form_factor")
    op.drop_column("devices", "os")
    op.drop_column("devices", "user_agent")
