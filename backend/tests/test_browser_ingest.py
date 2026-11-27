from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from alembic import command
from dabjob.config import Settings
from dabjob.main import create_app
from dabjob.models import IngestItem, IngestRun, Job

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
TOKEN = "test-token"
ORIGIN = "https://www.zhipin.com"

ITEM = {
    "platform": "boss",
    "page_kind": "detail",
    "url": "https://www.zhipin.com/job_detail/demo.html",
    "external_id": "demo-1",
    "title": "后端开发工程师",
    "company": "示例科技",
    "city": "上海",
    "salary_text": "25-40K",
    "seniority": "3-5年",
    "jd_text": "熟悉 Python 与 FastAPI。",
}


def _batch(**overrides: object) -> dict[str, object]:
    item = {**ITEM, **overrides}
    return {"adapter": "boss-detail", "adapter_version": 1, "items": [item]}


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[tuple[TestClient, FastAPI]]:
    settings = Settings(
        data_dir=tmp_path,
        host="127.0.0.1",
        allow_remote=False,
        static_dir=tmp_path / "no-build",
        token=TOKEN,
        allowed_origins=ORIGIN,
    )
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")

    app = create_app(settings)
    with TestClient(app) as client:
        yield client, app


def _post(client: TestClient, body: dict[str, object] | str) -> Any:
    payload = body if isinstance(body, str) else json.dumps(body)
    return client.post(
        "/api/ingest/browser",
        content=payload,
        headers={"origin": ORIGIN, "x-dabjob-token": TOKEN},
    )


def test_the_endpoint_is_disabled_without_a_token(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        host="127.0.0.1",
        static_dir=tmp_path / "no-build",
        token=None,
        allowed_origins=ORIGIN,
    )
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")

    with TestClient(create_app(settings)) as client:
        response = client.post("/api/ingest/browser", json=_batch())

    assert response.status_code == 503
    assert "DABJOB_TOKEN" in response.json()["detail"]


def test_the_endpoint_is_disabled_without_an_allowlist(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        host="127.0.0.1",
        static_dir=tmp_path / "no-build",
        token=TOKEN,
        allowed_origins="",
    )
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")

    with TestClient(create_app(settings)) as client:
        response = client.post("/api/ingest/browser", json=_batch())

    assert response.status_code == 503
    assert "DABJOB_ALLOWED_ORIGINS" in response.json()["detail"]


def test_a_missing_token_is_401(browser: tuple[TestClient, FastAPI]) -> None:
    client, _ = browser

    response = client.post(
        "/api/ingest/browser", content=json.dumps(_batch()), headers={"origin": ORIGIN}
    )

    assert response.status_code == 401


def test_a_wrong_token_is_401(browser: tuple[TestClient, FastAPI]) -> None:
    client, _ = browser

    response = client.post(
        "/api/ingest/browser",
        content=json.dumps(_batch()),
        headers={"origin": ORIGIN, "x-dabjob-token": "nope"},
    )

    assert response.status_code == 401


def test_a_foreign_origin_is_403(browser: tuple[TestClient, FastAPI]) -> None:
    client, _ = browser

    response = client.post(
        "/api/ingest/browser",
        content=json.dumps(_batch()),
        headers={"origin": "https://evil.example", "x-dabjob-token": TOKEN},
    )

    assert response.status_code == 403


def test_an_accepted_item_creates_a_job_and_a_run(
    browser: tuple[TestClient, FastAPI],
) -> None:
    client, app = browser

    response = _post(client, _batch())

    assert response.status_code == 200
    body = response.json()
    assert (body["accepted"], body["duplicates"], body["failed"]) == (1, 0, 0)

    with app.state.session_factory() as session:
        job = session.scalar(select(Job))
        run = session.scalar(select(IngestRun))
    assert job is not None and run is not None
    assert job.title == "后端开发工程师"
    assert job.company_name == "示例科技"
    assert run.adapter == "boss-detail@1"
    assert run.accepted == 1


def test_the_same_page_twice_is_a_duplicate(browser: tuple[TestClient, FastAPI]) -> None:
    client, app = browser
    _post(client, _batch())

    body = _post(client, _batch()).json()

    assert (body["accepted"], body["duplicates"]) == (0, 1)
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1


def test_a_text_plain_body_avoids_a_preflight(browser: tuple[TestClient, FastAPI]) -> None:
    """A simple request is the point: no OPTIONS, no blocked second hop."""
    client, _ = browser

    response = client.post(
        "/api/ingest/browser",
        content=json.dumps(_batch()),
        headers={
            "origin": ORIGIN,
            "x-dabjob-token": TOKEN,
            "content-type": "text/plain;charset=UTF-8",
        },
    )

    assert response.status_code == 200


def test_the_token_may_travel_in_the_query(browser: tuple[TestClient, FastAPI]) -> None:
    """Without a custom header the request stays a simple request."""
    client, _ = browser

    response = client.post(
        f"/api/ingest/browser?token={TOKEN}",
        content=json.dumps(_batch()),
        headers={"origin": ORIGIN, "content-type": "text/plain;charset=UTF-8"},
    )

    assert response.status_code == 200


def test_the_response_is_readable_by_the_page(browser: tuple[TestClient, FastAPI]) -> None:
    client, _ = browser

    response = _post(client, _batch())

    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_the_gate_cleans_the_item(browser: tuple[TestClient, FastAPI]) -> None:
    client, app = browser

    _post(client, _batch(title="后\u200b端工程师"))

    with app.state.session_factory() as session:
        job = session.scalar(select(Job))
        item = session.scalar(select(IngestItem))
    assert job is not None and item is not None
    assert job.title == "后端工程师"
    assert "zero_width_chars_removed:1" in item.gate_flags


def test_an_empty_title_after_the_gate_is_a_failed_item(
    browser: tuple[TestClient, FastAPI],
) -> None:
    client, app = browser

    body = _post(client, _batch(title="\u200b")).json()

    assert body["failed"] == 1
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0


def test_a_body_over_the_cap_is_413(browser: tuple[TestClient, FastAPI]) -> None:
    client, _ = browser
    huge = _batch(jd_text="x" * (300 * 1024))

    response = _post(client, huge)

    assert response.status_code == 413


def test_malformed_json_is_400(browser: tuple[TestClient, FastAPI]) -> None:
    client, _ = browser

    response = _post(client, "not json at all")

    assert response.status_code == 400


def test_a_preflight_from_an_allowed_origin_is_answered(
    browser: tuple[TestClient, FastAPI],
) -> None:
    client, _ = browser

    response = client.options(
        "/api/ingest/browser",
        headers={"origin": ORIGIN, "access-control-request-method": "POST"},
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "x-dabjob-token" in response.headers["access-control-allow-headers"]


def test_a_preflight_from_a_foreign_origin_is_refused(
    browser: tuple[TestClient, FastAPI],
) -> None:
    client, _ = browser

    response = client.options(
        "/api/ingest/browser",
        headers={"origin": "https://evil.example", "access-control-request-method": "POST"},
    )

    assert response.status_code == 403
