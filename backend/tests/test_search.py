"""Search runs against a migrated database, so the triggers under test are the
ones a user gets — not a test-only index."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dabjob.models import Job

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def client(api: tuple[TestClient, FastAPI]) -> tuple[TestClient, FastAPI]:
    return api


def _add_job(app: FastAPI, **fields: str) -> int:
    fields.setdefault("platform", "test")
    with app.state.session_factory() as session:
        job = Job(**fields)
        session.add(job)
        session.commit()
        return int(job.id)


def test_a_new_posting_is_indexed(client: tuple[TestClient, FastAPI]) -> None:
    test_client, app = client
    _add_job(
        app,
        title="后端开发工程师",
        company_name="示例科技",
        jd_text="熟悉 FastAPI 与 PostgreSQL，负责服务端接口。",
    )

    response = test_client.get("/api/jobs", params={"q": "FastAPI"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["company_name"] == "示例科技"
    assert "<mark>FastAPI</mark>" in body["items"][0]["snippet"]


def test_updating_a_title_reindexes(client: tuple[TestClient, FastAPI]) -> None:
    test_client, app = client
    job_id = _add_job(app, title="Backend Engineer", company_name="Acme", jd_text="Python")

    with app.state.session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        job.title = "Frontend Engineer"
        session.commit()

    assert test_client.get("/api/jobs", params={"q": "Backend"}).json()["total"] == 0
    assert test_client.get("/api/jobs", params={"q": "Frontend"}).json()["total"] == 1


def test_deleting_a_posting_removes_it_from_the_index(
    client: tuple[TestClient, FastAPI],
) -> None:
    test_client, app = client
    job_id = _add_job(app, title="Data Engineer", company_name="Acme", jd_text="Spark")

    with app.state.session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        session.delete(job)
        session.commit()

    assert test_client.get("/api/jobs", params={"q": "Spark"}).json()["total"] == 0


def test_company_name_is_searchable(client: tuple[TestClient, FastAPI]) -> None:
    test_client, app = client
    _add_job(app, title="Engineer", company_name="星尘网络", jd_text="Go")

    response = test_client.get("/api/jobs", params={"q": "星尘"})

    assert response.json()["total"] == 1


def test_two_character_query_falls_back_to_like(
    client: tuple[TestClient, FastAPI],
) -> None:
    """Trigram needs three characters; a short Chinese query must not be silent."""
    test_client, app = client
    _add_job(app, title="后端开发工程师", company_name="示例", jd_text="")

    assert test_client.get("/api/jobs", params={"q": "开发"}).json()["total"] == 1


@pytest.mark.parametrize("query", ['"', "*", "AND", "NEAR(", "a OR b", "-", "%"])
def test_hostile_query_text_is_not_an_expression(
    client: tuple[TestClient, FastAPI], query: str
) -> None:
    """FTS5 has its own syntax; user text must never be parsed as it."""
    test_client, _ = client

    response = test_client.get("/api/jobs", params={"q": query})

    assert response.status_code == 200


def test_empty_query_lists_recent_postings(client: tuple[TestClient, FastAPI]) -> None:
    test_client, app = client
    _add_job(app, title="First", company_name="A", jd_text="")
    _add_job(app, title="Second", company_name="B", jd_text="")

    body = test_client.get("/api/jobs").json()

    assert body["total"] == 2
    assert body["items"][0]["title"] == "Second"


def test_unknown_term_returns_nothing(client: tuple[TestClient, FastAPI]) -> None:
    test_client, app = client
    _add_job(app, title="Engineer", company_name="Acme", jd_text="Python")

    assert test_client.get("/api/jobs", params={"q": "Kubernetes"}).json()["total"] == 0
