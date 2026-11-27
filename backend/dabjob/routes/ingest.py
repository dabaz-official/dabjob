"""Ingest routes.

Paste is the only path that needs no browser and no adapter, which makes it
the first one to ship and the easiest one to test with a hostile fixture.
Every path goes through the integrity gate before anything is stored.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dedupe import fingerprint
from ..deps import get_session
from ..gate import MAX_TEXT_CHARS, inspect
from ..models import (
    IngestItem,
    IngestOutcome,
    IngestRun,
    IngestSource,
    IngestStatus,
    Job,
)
from ..parse import parse_job
from ..schemas import JobSummary

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

SessionDep = Annotated[Session, Depends(get_session)]


class PasteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    platform: str = Field(default="paste", min_length=1, max_length=64)
    source_url: str | None = Field(default=None, max_length=2000)


class PasteResult(BaseModel):
    run_id: int
    outcome: Literal["accepted", "duplicate"]
    job: JobSummary | None = None
    flags: list[str] = Field(default_factory=list)


@router.post("/paste")
def ingest_paste(payload: PasteRequest, session: SessionDep, response: Response) -> PasteResult:
    gate = inspect(payload.text)
    parsed = parse_job(gate.text)
    marker = fingerprint(payload.platform, None, parsed.company, parsed.title, parsed.city)

    run = IngestRun(source=IngestSource.PASTE, adapter="paste", status=IngestStatus.COMPLETED)
    session.add(run)
    session.flush()

    existing = session.scalar(select(Job).where(Job.fingerprint == marker))
    if existing is not None:
        run.duplicates = 1
        session.add(
            IngestItem(
                run_id=run.id,
                url=payload.source_url,
                outcome=IngestOutcome.DUPLICATE,
                raw_payload={"text": payload.text},
                gate_flags=list(gate.flags),
            )
        )
        session.commit()
        response.status_code = 200
        return PasteResult(
            run_id=run.id,
            outcome="duplicate",
            job=JobSummary.model_validate(existing),
            flags=list(gate.flags),
        )

    fallback_title = gate.text.strip().splitlines()[0][:120] if gate.text.strip() else ""
    job = Job(
        platform=payload.platform,
        url=payload.source_url,
        title=parsed.title or fallback_title,
        company_name=parsed.company or "",
        city=parsed.city,
        salary_min=parsed.salary_min,
        salary_max=parsed.salary_max,
        salary_text=parsed.salary_text,
        seniority=parsed.seniority,
        jd_text=gate.text,
        fingerprint=marker,
    )
    session.add(job)
    session.flush()

    run.accepted = 1
    session.add(
        IngestItem(
            run_id=run.id,
            url=payload.source_url,
            outcome=IngestOutcome.ACCEPTED,
            raw_payload={"text": payload.text},
            gate_flags=list(gate.flags),
        )
    )
    session.commit()

    response.status_code = 201
    return PasteResult(
        run_id=run.id,
        outcome="accepted",
        job=JobSummary.model_validate(job),
        flags=list(gate.flags),
    )
