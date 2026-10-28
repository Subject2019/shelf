from __future__ import annotations

from app.core.config import APP_VERSION


def test_health_returns_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == APP_VERSION
    assert payload["db"] == "ok"
    # 其他用例可能已写入书库，这里只校验字段类型与可用性
    assert isinstance(payload["libraries"], int)
    assert isinstance(payload["books"], int)
    assert isinstance(payload["ffmpeg"], bool)


def test_unknown_route_uses_error_envelope(client) -> None:
    response = client.get("/api/v1/not-exists")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
