from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_session
from ..models import Job
from ..schemas import JobList, JobSummary
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
