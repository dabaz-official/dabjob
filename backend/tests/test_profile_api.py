from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from dabjob.models import AgentTask

RESUME = (
    "张三\n"
    "后端工程师，五年经验。\n"
    "负责核心业务的服务端接口设计与开发，维护现有服务并推动性能优化。\n"
    "熟悉 Python 与 FastAPI，熟练使用 PostgreSQL，了解 Redis 与消息队列。"
)


def _upload(client: TestClient) -> None:
    response = client.post(
        "/api/profile/documents",
        files={"file": ("resume.md", RESUME.encode(), "text/markdown")},
    )
    assert response.status_code == 201


def test_reading_the_profile_creates_an_empty_one(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api

    body = client.get("/api/profile").json()

    assert body["target_roles"] == []
    assert body["target_cities"] == []
    assert body["salary_floor"] is None


def test_the_profile_can_be_saved_and_read_back(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api

    saved = client.put(
        "/api/profile",
        json={
            "years_experience": 5,
            "target_roles": ["后端工程师", "平台工程师"],
            "target_cities": ["上海", "杭州"],
            "salary_floor": 30000,
            "strengths": "服务拆分经验",
        },
    ).json()

    assert saved["target_roles"] == ["后端工程师", "平台工程师"]
    assert client.get("/api/profile").json()["salary_floor"] == 30000


def test_a_partial_update_leaves_other_fields_alone(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, _ = api
    client.put("/api/profile", json={"salary_floor": 30000, "years_experience": 5})

    body = client.put("/api/profile", json={"target_cities": ["深圳"]}).json()

    assert body["target_cities"] == ["深圳"]
    assert body["salary_floor"] == 30000
    assert body["years_experience"] == 5


def test_empty_entries_in_a_list_are_dropped(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api

    body = client.put("/api/profile", json={"target_roles": ["  后端  ", "", "   "]}).json()

    assert body["target_roles"] == ["后端"]


def test_an_assessment_needs_a_document(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api

    response = client.post("/api/profile/assessment")

    assert response.status_code == 400
    assert "résumé" in response.json()["detail"]


def test_the_manual_transport_returns_an_editable_draft(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, _ = api
    _upload(client)

    response = client.post("/api/profile/assessment")

    assert response.status_code == 200
    body = response.json()
    assert body["transport"] == "manual"
    assert body["strengths"] == []
    assert body["gaps"] == []
    assert body["positioning"] == ""
    assert body["task_id"] > 0


def test_an_assessment_does_not_touch_the_profile(
    api: tuple[TestClient, FastAPI],
) -> None:
    """A draft is a proposal; the profile changes when the user saves it."""
    client, _ = api
    _upload(client)
    client.put("/api/profile", json={"strengths": "我自己写的"})

    client.post("/api/profile/assessment")

    assert client.get("/api/profile").json()["strengths"] == "我自己写的"


def test_running_the_assessment_twice_is_recorded_twice(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    _upload(client)

    first = client.post("/api/profile/assessment").json()
    second = client.post("/api/profile/assessment").json()

    assert first["task_id"] != second["task_id"]
    with app.state.session_factory() as session:
        tasks = session.scalars(select(AgentTask)).all()
    assert len(tasks) == 2
    assert all(task.transport == "manual" for task in tasks)


def test_the_assessment_sends_the_resume_and_targets(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    _upload(client)
    client.put("/api/profile", json={"target_cities": ["上海"]})

    client.post("/api/profile/assessment")

    with app.state.session_factory() as session:
        task = session.scalar(select(AgentTask))
    assert task is not None
    assert task.input is not None
    assert "后端工程师" in task.input["resume_text"]
    assert task.input["target_cities"] == ["上海"]


def test_an_unimplemented_transport_is_reported_as_unavailable(
    api: tuple[TestClient, FastAPI], tmp_path: Path
) -> None:
    client, app = api
    _upload(client)
    app.state.settings.agent_provider = "http"

    response = client.post("/api/profile/assessment")

    assert response.status_code == 503
    assert "not implemented" in response.json()["detail"]


def test_positioning_and_target_fit_survive_a_save(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, _ = api

    client.put(
        "/api/profile",
        json={"positioning": "能把业务问题翻译成服务边界的人", "target_fit": "平台与基础设施"},
    )

    body = client.get("/api/profile").json()
    assert body["positioning"] == "能把业务问题翻译成服务边界的人"
    assert body["target_fit"] == "平台与基础设施"
