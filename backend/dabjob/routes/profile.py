"""The profile: the one row that says who is looking for work, plus the
documents it is built from.

The assessment endpoint proposes; it never writes the profile. The user
edits the draft and saves it, so a model's guess cannot silently become the
record it is scored against.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import make_transport
from ..agents.base import TaskEnvelope
from ..agents.runner import run_task
from ..deps import get_session
from ..documents import EmptyDocument, UnsupportedDocument, extract_text
from ..models import AgentTaskStatus, DocumentKind, Profile, ProfileDocument
from ..schemas import (
    AssessmentDraft,
    ProfileDocumentDetail,
    ProfileDocumentSummary,
    ProfileOut,
    ProfileUpdate,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


# ── Documents ──────────────────────────────────────────────────────────────


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


# ── Profile ────────────────────────────────────────────────────────────────


def _profile(session: Session) -> Profile:
    """There is exactly one profile; reading it creates the empty row."""
    profile = session.scalar(select(Profile).limit(1))
    if profile is None:
        profile = Profile(target_roles=[], target_cities=[])
        session.add(profile)
        session.commit()
    return profile


@router.get("")
def get_profile(session: SessionDep) -> ProfileOut:
    return ProfileOut.model_validate(_profile(session))


@router.put("")
def update_profile(payload: ProfileUpdate, session: SessionDep) -> ProfileOut:
    profile = _profile(session)

    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if field in ("target_roles", "target_cities") and value is not None:
            value = [item.strip() for item in value if item.strip()]
        setattr(profile, field, value)

    session.commit()
    return ProfileOut.model_validate(profile)


@router.post("/assessment")
def create_assessment(request: Request, session: SessionDep) -> AssessmentDraft:
    """Run the profile task through the configured transport.

    With the default `manual` transport the draft is empty by design: every
    field is there to be filled in, and they are the same fields a model
    would have written.
    """
    profile = _profile(session)
    document = session.scalar(
        select(ProfileDocument).order_by(ProfileDocument.created_at.desc()).limit(1)
    )
    if document is None or not (document.extracted_text or "").strip():
        raise HTTPException(
            status_code=400, detail="upload a résumé before asking for an assessment"
        )

    try:
        transport = make_transport(request.app.state.settings)
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    envelope = TaskEnvelope(
        task="analyze_profile",
        input={
            "resume_text": document.extracted_text,
            "target_roles": profile.target_roles,
            "target_cities": profile.target_cities,
            "salary_floor": profile.salary_floor,
            "years_experience": profile.years_experience,
        },
    )
    task = run_task(session, transport, envelope)

    if task.status is not AgentTaskStatus.SUCCEEDED or task.output is None:
        raise HTTPException(
            status_code=502, detail=task.error or "the transport did not return a usable answer"
        )

    return AssessmentDraft(task_id=task.id, transport=task.transport, **task.output)
