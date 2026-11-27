"""Route for profile documents. Upload is multipart, extraction is local."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_session
from ..documents import EmptyDocument, UnsupportedDocument, extract_text
from ..models import DocumentKind, ProfileDocument
from ..schemas import ProfileDocumentDetail, ProfileDocumentSummary

router = APIRouter(prefix="/api/profile", tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _summary(document: ProfileDocument) -> ProfileDocumentSummary:
    return ProfileDocumentSummary(
        id=document.id,
        kind=document.kind,
        filename=document.filename,
        content_type=document.content_type,
        char_count=len(document.extracted_text or ""),
        created_at=document.created_at,
    )


@router.get("/documents")
def list_documents(session: SessionDep) -> list[ProfileDocumentSummary]:
    documents = session.scalars(
        select(ProfileDocument).order_by(ProfileDocument.created_at.desc())
    ).all()
    return [_summary(document) for document in documents]


@router.get("/documents/{document_id}")
def get_document(document_id: int, session: SessionDep) -> ProfileDocumentDetail:
    document = session.get(ProfileDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")

    return ProfileDocumentDetail(
        **_summary(document).model_dump(),
        extracted_text=document.extracted_text or "",
    )


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    kind: Annotated[DocumentKind, Form()] = DocumentKind.RESUME,
) -> ProfileDocumentSummary:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file is larger than 10 MB")

    try:
        text = extract_text(file.filename or "", data)
    except (UnsupportedDocument, EmptyDocument) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    document = ProfileDocument(
        kind=kind,
        filename=file.filename or "upload",
        content_type=file.content_type,
        extracted_text=text,
    )
    session.add(document)
    session.commit()
    return _summary(document)
