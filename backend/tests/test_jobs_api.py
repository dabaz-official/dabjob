from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from dabjob.models import Application, ApplicationEvent, EventKind, Job, PipelineStatus


def _seed_job(client: TestClient, **overrides: str) -> int:
    payload = {"text": "岗位：后端工程师\n公司：示例科技\n城市：上海\n熟悉 FastAPI。"}
    payload.update(overrides)
    response = client.post("/api/ingest/paste", json=payload)
    assert response.status_code == 201
    return int(response.json()["job"]["id"])


def test_a_job_can_be_fetched(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    job_id = _seed_job(client)

    response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "后端工程师"


def test_an_unknown_job_is_404(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api

    assert client.get("/api/jobs/9999").status_code == 404
    assert client.patch("/api/jobs/9999", json={"title": "x"}).status_code == 404
    assert client.delete("/api/jobs/9999").status_code == 404


def test_renaming_a_job_updates_the_search_index(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    # The stored JD deliberately does not contain the title, so a hit after
    # the rename can only come from the title column of the index.
    with app.state.session_factory() as session:
        job = Job(
            platform="test",
            title="Backend Engineer",
            company_name="Acme",
            jd_text="Python only",
        )
        session.add(job)
        session.commit()
        job_id = job.id

    assert client.get("/api/jobs", params={"q": "Backend"}).json()["total"] == 1

    response = client.patch(f"/api/jobs/{job_id}", json={"title": "Frontend Engineer"})

    assert response.status_code == 200
    assert client.get("/api/jobs", params={"q": "Frontend"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "Backend"}).json()["total"] == 0


def test_a_partial_update_leaves_other_fields_alone(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, _ = api
    job_id = _seed_job(client)

    response = client.patch(f"/api/jobs/{job_id}", json={"title": "改名后的岗位"})

    body = response.json()
    assert body["title"] == "改名后的岗位"
    assert body["company_name"] == "示例科技"
    assert body["city"] == "上海"


def test_a_field_set_to_null_is_cleared(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    job_id = _seed_job(client)

    body = client.patch(f"/api/jobs/{job_id}", json={"city": None}).json()

    assert body["city"] is None


def test_an_empty_title_is_rejected(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    job_id = _seed_job(client)

    assert client.patch(f"/api/jobs/{job_id}", json={"title": ""}).status_code == 422


def test_deleting_a_job_removes_it_and_its_application(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    job_id = _seed_job(client)
    with app.state.session_factory() as session:
        session.add(Application(job_id=job_id, status=PipelineStatus.APPLIED))
        session.commit()

    response = client.delete(f"/api/jobs/{job_id}")

    assert response.status_code == 204
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        # ondelete="CASCADE" plus PRAGMA foreign_keys=ON does the rest.
        assert session.scalar(select(func.count()).select_from(Application)) == 0


def test_deleting_a_job_removes_it_from_the_index(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, _ = api
    job_id = _seed_job(client)

    client.delete(f"/api/jobs/{job_id}")

    assert client.get("/api/jobs", params={"q": "FastAPI"}).json()["total"] == 0


def test_applications_can_be_listed_and_filtered(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    first = _seed_job(client)
    second = _seed_job(client, text="岗位：分析师\n公司：另一家\n熟悉 SQL。")
    with app.state.session_factory() as session:
        session.add(Application(job_id=first, status=PipelineStatus.APPLIED))
        session.add(Application(job_id=second, status=PipelineStatus.INTERVIEW))
        session.commit()

    everything = client.get("/api/applications").json()
    interviewing = client.get("/api/applications", params={"status": "interview"}).json()

    assert everything["total"] == 2
    assert interviewing["total"] == 1
    assert interviewing["items"][0]["status"] == "interview"


def test_changing_a_status_records_an_event(api: tuple[TestClient, FastAPI]) -> None:
    client, app = api
    job_id = _seed_job(client)
    with app.state.session_factory() as session:
        application = Application(job_id=job_id, status=PipelineStatus.APPLIED)
        session.add(application)
        session.commit()
        application_id = application.id

    response = client.patch(f"/api/applications/{application_id}", json={"status": "interview"})

    assert response.status_code == 200
    assert response.json()["status"] == "interview"
    with app.state.session_factory() as session:
        event = session.scalar(select(ApplicationEvent))
    assert event is not None
    assert event.kind is EventKind.INTERVIEW
    assert event.body == "applied -> interview"


def test_a_status_without_a_milestone_is_recorded_as_a_note(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    job_id = _seed_job(client)
    with app.state.session_factory() as session:
        application = Application(job_id=job_id, status=PipelineStatus.APPLIED)
        session.add(application)
        session.commit()
        application_id = application.id

    client.patch(f"/api/applications/{application_id}", json={"status": "ghosted"})

    with app.state.session_factory() as session:
        event = session.scalar(select(ApplicationEvent))
    assert event is not None
    assert event.kind is EventKind.NOTE


def test_a_follow_up_date_can_be_set(api: tuple[TestClient, FastAPI]) -> None:
    client, app = api
    job_id = _seed_job(client)
    with app.state.session_factory() as session:
        application = Application(job_id=job_id, status=PipelineStatus.APPLIED)
        session.add(application)
        session.commit()
        application_id = application.id

    body = client.patch(
        f"/api/applications/{application_id}", json={"next_follow_up_on": "2026-12-01"}
    ).json()

    assert body["next_follow_up_on"] == "2026-12-01"


def test_an_unknown_status_is_rejected(api: tuple[TestClient, FastAPI]) -> None:
    client, app = api
    job_id = _seed_job(client)
    with app.state.session_factory() as session:
        application = Application(job_id=job_id, status=PipelineStatus.APPLIED)
        session.add(application)
        session.commit()
        application_id = application.id

    assert (
        client.patch(f"/api/applications/{application_id}", json={"status": "hired"}).status_code
        == 422
    )


def test_an_unknown_application_is_404(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api

    assert client.patch("/api/applications/9999", json={"status": "applied"}).status_code == 404


@pytest.mark.parametrize("field", ["title", "company_name", "city"])
def test_gate_cleans_nothing_on_a_trusted_edit(api: tuple[TestClient, FastAPI], field: str) -> None:
    """User edits are trusted input; the gate is for postings, not for the
    person editing their own record."""
    client, _ = api
    job_id = _seed_job(client)

    body = client.patch(f"/api/jobs/{job_id}", json={field: "我的公司"}).json()

    assert body[field] == "我的公司"


def test_an_application_can_be_created(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    job_id = _seed_job(client)

    response = client.post("/api/applications", json={"job_id": job_id})

    assert response.status_code == 201
    assert response.json()["status"] == "saved"
    assert client.get("/api/applications").json()["total"] == 1


def test_a_job_cannot_enter_the_pipeline_twice(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    job_id = _seed_job(client)
    client.post("/api/applications", json={"job_id": job_id})

    response = client.post("/api/applications", json={"job_id": job_id})

    assert response.status_code == 409


def test_an_application_for_an_unknown_job_is_404(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, _ = api

    assert client.post("/api/applications", json={"job_id": 9999}).status_code == 404


def test_an_application_can_be_deleted(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    job_id = _seed_job(client)
    application_id = client.post("/api/applications", json={"job_id": job_id}).json()["id"]

    response = client.delete(f"/api/applications/{application_id}")

    assert response.status_code == 204
    assert client.get("/api/applications").json()["total"] == 0
    # The posting itself stays.
    assert client.get(f"/api/jobs/{job_id}").status_code == 200
