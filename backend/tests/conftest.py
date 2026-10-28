"""测试夹具：临时数据目录 + 已迁移数据库 + TestClient，避免污染项目 data/。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP_ROOT = tempfile.mkdtemp(prefix="echoshelf-test-")
os.environ["ECHOSHELF_DATA_PATH"] = _TMP_ROOT
os.environ.setdefault("AUDIOBOOKS_PATH", os.path.join(_TMP_ROOT, "audiobooks"))
os.environ.setdefault("ECHOSHELF_LOG_LEVEL", "warning")
# 测试样本只有几十 KB，关掉扫描的最小体积过滤
os.environ.setdefault("ECHOSHELF_SCAN_MIN_SIZE_BYTES", "0")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import dispose_engine  # noqa: E402
from app.main import app  # noqa: E402

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture(scope="session")
def database():
    dispose_engine()
    command.upgrade(AlembicConfig(str(ALEMBIC_INI)), "head")
    yield
    dispose_engine()


@pytest.fixture(scope="session")
def client(database):
    with TestClient(app) as test_client:
        yield test_client
