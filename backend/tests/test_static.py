from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dabjob.config import Settings
from dabjob.main import create_app


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    (build / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return build


@pytest.fixture
def client(tmp_path: Path, dist: Path) -> Iterator[TestClient]:
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            host="127.0.0.1",
            allow_remote=False,
            static_dir=dist,
        )
    )
    with TestClient(app) as test_client:
        yield test_client


def test_root_serves_the_built_index(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "<title>spa</title>" in response.text


def test_assets_are_served_from_the_build(client: TestClient) -> None:
    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"


def test_client_route_falls_back_to_index(client: TestClient) -> None:
    response = client.get("/jobs/42")

    assert response.status_code == 200
    assert "<title>spa</title>" in response.text


def test_api_routes_still_win(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"ok": True}


def test_unknown_api_path_is_not_a_page(client: TestClient) -> None:
    assert client.get("/api/does-not-exist").status_code == 404


def test_path_traversal_does_not_escape_the_build(tmp_path: Path, client: TestClient) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")

    response = client.get("/../secret.txt")

    assert "private" not in response.text


def test_no_build_means_no_spa_routes(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            host="127.0.0.1",
            allow_remote=False,
            static_dir=tmp_path / "missing",
        )
    )

    with TestClient(app) as test_client:
        assert test_client.get("/").status_code == 404
        assert test_client.get("/api/health").json() == {"ok": True}
