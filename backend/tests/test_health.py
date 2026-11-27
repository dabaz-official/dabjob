from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from dabjob.config import Settings
from dabjob.main import create_app


def test_health_returns_ok(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, host="127.0.0.1", allow_remote=False))

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
