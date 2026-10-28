"""add devices.revoked_at

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24 23:55:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 非空表示该设备已被踢下线：其 access token 立即失效，refresh token 一并吊销
    op.add_column("devices", sa.Column("revoked_at", sa.Integer(), nullable=True))
    op.create_index("idx_devices_user", "devices", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_devices_user", table_name="devices")
    op.drop_column("devices", "revoked_at")
