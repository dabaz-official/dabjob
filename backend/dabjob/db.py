"""SQLite access: one engine, two pragmas, no ORM magic at import time."""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from .config import Settings


def build_engine(settings: Settings) -> Engine:
    """Create the engine for ``settings.database_url`` and apply pragmas.

    WAL keeps a read from blocking a write while the UI polls, and
    ``foreign_keys`` is off by default in SQLite — it has to be set on every
    connection, which is why it lives in a connect listener rather than a
    one-off statement.
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    return engine
