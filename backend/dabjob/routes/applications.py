"""Applications: the pipeline side of a posting.

Changing a status writes an event. The event kind is the milestone itself
where one exists (applied, interview, offer, rejected) and a note otherwise,
so the timeline reads as history rather than as a change log.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_session
from ..models import Application, ApplicationEvent, EventKind, Job, PipelineStatus
from ..schemas import (
    ApplicationCreate,
    ApplicationList,
    ApplicationSummary,
    ApplicationUpdate,
)

router = APIRouter(prefix="/api", tags=["applications"])

SessionDep = Annotated[Session, Depends(get_session)]

STATUS_EVENT: dict[PipelineStatus, EventKind] = {
    PipelineStatus.APPLIED: EventKind.APPLIED,
    PipelineStatus.INTERVIEW: EventKind.INTERVIEW,
    PipelineStatus.OFFER: EventKind.OFFER,
    PipelineStatus.REJECTED: EventKind.REJECTED,
}


@router.get("/applications")
def list_applications(
    session: SessionDep,
    status_filter: Annotated[PipelineStatus | None, Query(alias="status")] = None,
) -> ApplicationList:
    statement = select(Application).order_by(Application.updated_at.desc(), Application.id.desc())
    if status_filter is not None:
        statement = statement.where(Application.status == status_filter)

    applications = session.scalars(statement).all()
    return ApplicationList(
        items=[ApplicationSummary.model_validate(item) for item in applications],
        total=len(applications),
    )


@router.post("/applications", status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, session: SessionDep) -> ApplicationSummary:
    """Add a posting to the pipeline. A job has one application at most."""
    if session.get(Job, payload.job_id) is None:
        raise HTTPException(status_code=404, detail=f"job {payload.job_id} not found")

    existing = session.scalar(select(Application).where(Application.job_id == payload.job_id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="this job is already in the pipeline")

    application = Application(job_id=payload.job_id, status=payload.status)
    session.add(application)
    session.commit()
    return ApplicationSummary.model_validate(application)


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, session: SessionDep) -> Response:
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"application {application_id} not found")

    session.delete(application)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/applications/{application_id}")
def update_application(
    application_id: int, payload: ApplicationUpdate, session: SessionDep
) -> ApplicationSummary:
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"application {application_id} not found")

    previous = application.status
    for field in payload.model_fields_set:
        setattr(application, field, getattr(payload, field))

    if application.status is not previous:
        session.add(
            ApplicationEvent(
                application_id=application.id,
                kind=STATUS_EVENT.get(application.status, EventKind.NOTE),
                body=f"{previous.value} -> {application.status.value}",
            )
        )

    session.commit()
    return ApplicationSummary.model_validate(application)
