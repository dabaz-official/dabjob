"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    """One session per request, from the factory created at startup."""
    factory = request.app.state.session_factory
    with factory() as session:
        yield session
