from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_session
from ..models import Job
from ..schemas import JobList, JobSummary, JobUpdate
from ..search import search_jobs

router = APIRouter(prefix="/api", tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/jobs")
def list_jobs(
    session: SessionDep,
    q: Annotated[str | None, Query(description="Full-text query")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> JobList:
    if q:
        hits = search_jobs(session, q, limit)
        return JobList(
            items=[
                JobSummary.model_validate(hit.job).model_copy(update={"snippet": hit.snippet})
                for hit in hits
            ],
            total=len(hits),
        )

    jobs = session.scalars(
        select(Job).order_by(Job.created_at.desc(), Job.id.desc()).limit(limit)
    ).all()
    return JobList(items=[JobSummary.model_validate(job) for job in jobs], total=len(jobs))


@router.get("/jobs/{job_id}")
def get_job(job_id: int, session: SessionDep) -> JobSummary:
    return JobSummary.model_validate(_job_or_404(session, job_id))


@router.patch("/jobs/{job_id}")
def update_job(job_id: int, payload: JobUpdate, session: SessionDep) -> JobSummary:
    job = _job_or_404(session, job_id)

    for field in payload.model_fields_set:
        setattr(job, field, getattr(payload, field))

    session.commit()
    # The FTS index follows from the trigger on `job`, so a retitled posting
    # is searchable under the new title without a rebuild.
    return JobSummary.model_validate(job)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, session: SessionDep) -> Response:
    job = _job_or_404(session, job_id)
    session.delete(job)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _job_or_404(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return job
