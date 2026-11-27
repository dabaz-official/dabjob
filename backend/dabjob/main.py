"""The application factory.

The bind policy runs in the lifespan rather than at import time: an import
must never fail because of the environment, and a startup must fail loudly
when the bind address would expose the database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, enforce_bind_policy
from .db import build_engine, build_sessionmaker
from .deps import get_session
from .models import Job
from .schemas import JobList, JobSummary
from .search import search_jobs
from .static import mount_spa

SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    enforce_bind_policy(app.state.settings)
    yield
    app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    app = FastAPI(
        title="DabJob",
        version="0.0.1",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    engine = build_engine(resolved)
    app.state.settings = resolved
    app.state.engine = engine
    app.state.session_factory = build_sessionmaker(engine)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/jobs")
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

    mount_spa(app, resolved.static_dir)

    return app


app = create_app()
