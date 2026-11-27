from __future__ import annotations

import io
from pathlib import Path

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dabjob.documents import (
    EmptyDocument,
    UnsupportedDocument,
    extract_text,
    normalise,
)

FIXTURES = Path(__file__).parent / "fixtures" / "documents"

# Long enough to clear the scan-detection threshold, which exists so an
# image-only PDF cannot quietly become an empty document.
RESUME_ZH = (
    "张三\n"
    "后端工程师，五年经验。\n"
    "负责核心业务的服务端接口设计与开发，维护现有服务并推动性能优化。\n"
    "熟悉 Python 与 FastAPI，熟练使用 PostgreSQL，了解 Redis 与消息队列。\n"
    "参与过从零搭建的服务拆分，把单体应用迁移为三个独立服务。"
)


def _docx_bytes(paragraphs: list[str]) -> bytes:
    document = Document()
    for line in paragraphs:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_markdown_is_read_as_text() -> None:
    text = extract_text("resume.md", ("# " + RESUME_ZH).encode())

    assert text.startswith("# 张三")
    assert "后端工程师" in text


def test_docx_paragraphs_and_tables_are_read() -> None:
    data = _docx_bytes(RESUME_ZH.split("\n"))

    text = extract_text("resume.docx", data)

    assert "张三" in text
    assert "PostgreSQL" in text
    assert "FastAPI" in text


def test_a_pdf_is_read() -> None:
    data = (FIXTURES / "resume-en.pdf").read_bytes()

    text = extract_text("resume.pdf", data)

    assert "Backend engineer, five years" in text
    assert "PostgreSQL" in text


def test_an_unsupported_type_is_refused() -> None:
    with pytest.raises(UnsupportedDocument, match="not supported"):
        extract_text("resume.pages", b"\x00\x01")


def test_a_scan_like_document_fails_explicitly() -> None:
    with pytest.raises(EmptyDocument, match="OCR"):
        extract_text("scan.md", b"   \n\n  ")


def test_broken_bytes_are_refused_not_guessed() -> None:
    with pytest.raises(UnsupportedDocument, match="not UTF-8"):
        extract_text("resume.txt", b"\xff\xfe\x00")


def test_normalise_collapses_padding() -> None:
    text = normalise("a   \n\n\n\nb\x0c\nc   ")

    assert text == "a\n\nb\n\nc"


@pytest.fixture
def client(api: tuple[TestClient, FastAPI]) -> tuple[TestClient, FastAPI]:
    return api


def test_upload_stores_the_extracted_text(client: tuple[TestClient, FastAPI]) -> None:
    http, app = client

    response = http.post(
        "/api/profile/documents",
        files={"file": ("resume.md", RESUME_ZH.encode(), "text/markdown")},
        data={"kind": "resume"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "resume.md"
    assert body["char_count"] > 10

    with app.state.session_factory() as session:
        from dabjob.models import ProfileDocument

        stored = session.query(ProfileDocument).one()
    assert "后端工程师" in (stored.extracted_text or "")


def test_upload_accepts_a_pdf(client: tuple[TestClient, FastAPI]) -> None:
    http, _ = client
    data = (FIXTURES / "resume-en.pdf").read_bytes()

    response = http.post(
        "/api/profile/documents",
        files={"file": ("resume.pdf", data, "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["char_count"] > 50


def test_upload_refuses_an_empty_scan(client: tuple[TestClient, FastAPI]) -> None:
    http, _ = client

    response = http.post(
        "/api/profile/documents",
        files={"file": ("scan.md", b"   ", "text/markdown")},
    )

    assert response.status_code == 400
    assert "OCR" in response.json()["detail"]


def test_upload_refuses_an_unsupported_type(client: tuple[TestClient, FastAPI]) -> None:
    http, _ = client

    response = http.post(
        "/api/profile/documents",
        files={"file": ("resume.pages", b"whatever", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_documents_can_be_listed(client: tuple[TestClient, FastAPI]) -> None:
    http, _ = client
    http.post(
        "/api/profile/documents",
        files={"file": ("a.md", ("第一份材料。" + RESUME_ZH).encode(), "text/markdown")},
    )
    http.post(
        "/api/profile/documents",
        files={"file": ("b.md", ("第二份材料。" + RESUME_ZH).encode(), "text/markdown")},
    )

    body = http.get("/api/profile/documents").json()

    assert len(body) == 2
    assert {item["filename"] for item in body} == {"a.md", "b.md"}


def test_the_extracted_text_can_be_read_back(client: tuple[TestClient, FastAPI]) -> None:
    http, _ = client
    created = http.post(
        "/api/profile/documents",
        files={"file": ("resume.md", RESUME_ZH.encode(), "text/markdown")},
    ).json()

    response = http.get(f"/api/profile/documents/{created['id']}")

    assert response.status_code == 200
    assert "张三" in response.json()["extracted_text"]


def test_an_unknown_document_is_404(client: tuple[TestClient, FastAPI]) -> None:
    http, _ = client

    assert http.get("/api/profile/documents/9999").status_code == 404


def test_spaces_between_chinese_characters_are_removed() -> None:
    """A PDF positions glyphs, so "主 导从" arrives spaced; Chinese never is."""
    assert normalise("主 导从 Next.js 到 Shopify 的迁移") == "主导从 Next.js 到 Shopify 的迁移"


def test_wrongly_spaced_punctuation_is_joined() -> None:
    assert normalise("工作风格 ，统一工具配置 。") == "工作风格，统一工具配置。"


def test_a_space_between_chinese_and_latin_is_kept() -> None:
    """That space is real typography, not an artefact."""
    assert normalise("熟悉 Python 与 PostgreSQL") == "熟悉 Python 与 PostgreSQL"


def test_line_breaks_are_not_joined() -> None:
    assert normalise("第一行\n第二行") == "第一行\n第二行"
