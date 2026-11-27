from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from dabjob.models import Application, IngestItem, Job, PipelineStatus
from dabjob.tabular import read_table, suggest_mapping

CSV_ZH = """岗位,公司,城市,薪资,状态,链接
后端开发工程师,示例科技,上海,25-40K,已投递,https://example.com/a
数据分析师,星尘网络,北京,18-28K,面试中,https://example.com/b
平台工程师,蓝港,深圳,30-45K,已拒,https://example.com/c
"""


def _count(app: FastAPI, model: type) -> int:
    with app.state.session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_csv_headers_are_read() -> None:
    table = read_table(CSV_ZH)

    assert table.headers == ("岗位", "公司", "城市", "薪资", "状态", "链接")
    assert len(table.rows) == 3


def test_json_array_is_read() -> None:
    text = json.dumps([{"title": "Engineer", "company": "Acme"}, {"title": "Analyst"}])

    table = read_table(text)

    assert table.headers == ("title", "company")
    assert table.rows[1]["company"] == ""


def test_mapping_is_suggested_from_chinese_headers() -> None:
    table = read_table(CSV_ZH)

    mapping = suggest_mapping(table.headers)

    assert mapping["title"] == "岗位"
    assert mapping["company"] == "公司"
    assert mapping["city"] == "城市"
    assert mapping["status"] == "状态"


def test_preview_reports_headers_and_a_guess(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api

    response = client.post("/api/ingest/tabular/preview", json={"text": CSV_ZH})

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 3
    assert body["suggested_mapping"]["title"] == "岗位"
    assert body["sample"][0]["公司"] == "示例科技"


def test_import_creates_jobs_and_applications(api: tuple[TestClient, FastAPI]) -> None:
    client, app = api

    response = client.post("/api/ingest/tabular", json={"text": CSV_ZH})

    assert response.status_code == 200
    body = response.json()
    assert (body["accepted"], body["duplicates"], body["failed"]) == (3, 0, 0)
    assert _count(app, Job) == 3
    assert _count(app, Application) == 3

    with app.state.session_factory() as session:
        statuses = sorted(
            session.scalars(select(Application.status)).all(), key=lambda item: item.value
        )
    assert statuses == [
        PipelineStatus.APPLIED,
        PipelineStatus.INTERVIEW,
        PipelineStatus.REJECTED,
    ]


def test_the_same_file_imported_twice_adds_nothing(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api

    client.post("/api/ingest/tabular", json={"text": CSV_ZH})
    second = client.post("/api/ingest/tabular", json={"text": CSV_ZH})

    assert second.json()["duplicates"] == 3
    assert second.json()["accepted"] == 0
    assert _count(app, Job) == 3
    assert _count(app, Application) == 3


def test_a_hundred_rows_make_a_hundred_applications(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    lines = ["岗位,公司,状态"]
    lines += [f"职位 {index},公司 {index},已投递" for index in range(100)]

    response = client.post("/api/ingest/tabular", json={"text": "\n".join(lines)})

    assert response.json()["accepted"] == 100
    assert _count(app, Job) == 100
    assert _count(app, Application) == 100


def test_an_unknown_status_fails_only_that_row(api: tuple[TestClient, FastAPI]) -> None:
    client, app = api
    text = "岗位,公司,状态\nA,甲,已投递\nB,乙,不存在的状态\nC,丙,面试中"

    response = client.post("/api/ingest/tabular", json={"text": text})

    body = response.json()
    assert (body["accepted"], body["failed"]) == (2, 1)
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"].startswith("unknown_status:")

    with app.state.session_factory() as session:
        failed = session.scalars(select(IngestItem).where(IngestItem.error.is_not(None))).all()
    assert len(failed) == 1


def test_a_row_without_a_title_fails(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api

    response = client.post("/api/ingest/tabular", json={"text": "岗位,公司\n,没有标题的公司"})

    assert response.json()["failed"] == 1
    assert response.json()["errors"][0]["error"] == "missing_title"


def test_a_mapping_can_be_given_explicitly(api: tuple[TestClient, FastAPI]) -> None:
    client, app = api
    text = "role,employer\nEngineer,Acme"

    response = client.post(
        "/api/ingest/tabular",
        json={"text": text, "mapping": {"title": "role", "company": "employer"}},
    )

    assert response.json()["accepted"] == 1
    with app.state.session_factory() as session:
        job = session.scalar(select(Job))
    assert job is not None
    assert (job.title, job.company_name) == ("Engineer", "Acme")


def test_a_mapping_naming_a_missing_column_is_rejected(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, _ = api

    response = client.post(
        "/api/ingest/tabular",
        json={"text": "岗位\nA", "mapping": {"title": "不存在的列"}},
    )

    assert response.status_code == 400
    assert "不存在的列" in response.json()["detail"]


def test_invisible_characters_in_a_cell_are_removed(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    text = "岗位,公司\n后\u200b端工程师,示例"

    client.post("/api/ingest/tabular", json={"text": text})

    with app.state.session_factory() as session:
        job = session.scalar(select(Job))
    assert job is not None
    assert job.title == "后端工程师"


@pytest.mark.parametrize("payload", ["", "   ", "not json {", "[1, 2]"])
def test_unreadable_input_is_a_client_error(api: tuple[TestClient, FastAPI], payload: str) -> None:
    client, _ = api

    response = client.post("/api/ingest/tabular", json={"text": payload})

    assert response.status_code in {400, 422}
