"""The application factory.

The bind policy runs in the lifespan rather than at import time: an import
must never fail because of the environment, and a startup must fail loudly
when the bind address would expose the database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings, enforce_bind_policy
from .db import build_engine, build_sessionmaker
from .routes import applications, health, ingest, jobs
from .static import mount_spa


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

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(applications.router)
    app.include_router(ingest.router)

    mount_spa(app, resolved.static_dir)

    return app


app = create_app()
