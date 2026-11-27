"""The schema exists in two places — the models and the migration — and this
file is what keeps them honest.

A migration that drifts from the models is the failure mode that only shows
up on a user's upgrade, months later, with their data in it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from dabjob.config import Settings
from dabjob.db import build_engine, build_sessionmaker
from dabjob.migration_support import include_object
from dabjob.models import Application, Base, Company, Job, PipelineStatus

EXPECTED_TABLES = {
    "agent_action",
    "agent_task",
    "application",
    "application_event",
    "company",
    "ingest_item",
    "ingest_run",
    "job",
    "job_analysis",
    "job_skill",
    "profile",
    "profile_document",
    "setting",
    "skill",
}

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _migrate(url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest.fixture
def migrated_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    _migrate(url)
    return url


@pytest.fixture
def db(tmp_path: Path) -> Iterator[tuple[Engine, sessionmaker[Session]]]:
    engine = build_engine(
        Settings(data_dir=tmp_path, host="127.0.0.1", allow_remote=False, static_dir=tmp_path)
    )
    Base.metadata.create_all(engine)
    yield engine, build_sessionmaker(engine)
    engine.dispose()


def test_models_declare_every_table() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_migration_creates_the_same_tables(migrated_url: str) -> None:
    engine = create_engine(migrated_url)

    tables = {
        name
        for name in inspect(engine).get_table_names()
        if not name.startswith("job_fts") and name != "alembic_version"
    }

    assert tables == EXPECTED_TABLES
    assert inspect(engine).get_table_names().count("job_fts") == 1


def test_migration_matches_the_models(migrated_url: str) -> None:
    engine = create_engine(migrated_url)

    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object": include_object})
        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_foreign_keys_are_enforced(db: tuple[Engine, sessionmaker[Session]]) -> None:
    """SQLite defaults to ignoring foreign keys; ``build_engine`` must not."""
    _, session_factory = db

    with session_factory() as session, pytest.raises(IntegrityError):
        session.add(Job(company_id=9999, platform="test", title="Orphan"))
        session.commit()


def test_enums_are_stored_as_values(db: tuple[Engine, sessionmaker[Session]]) -> None:
    engine, session_factory = db

    with session_factory() as session:
        session.add(Company(name="Example"))
        session.flush()
        session.add(Job(platform="boss", title="Backend engineer"))
        session.flush()
        session.add(Application(job_id=1))
        session.commit()

    with engine.connect() as connection:
        stored = connection.execute(text("SELECT status FROM application")).scalar_one()

    # 'saved', not 'SAVED': a database you can read without the app.
    assert stored == PipelineStatus.SAVED.value == "saved"


def test_timestamps_round_trip_as_utc(db: tuple[Engine, sessionmaker[Session]]) -> None:
    """SQLite drops tzinfo; the type decorator has to put it back."""
    engine, session_factory = db

    with session_factory() as session:
        job = Job(platform="boss", title="Backend engineer")
        session.add(job)
        session.commit()
        job_id = job.id

    with engine.connect() as connection:
        stored = connection.execute(text("SELECT captured_at FROM job")).scalar_one()
    # Written as a naive UTC string: SQLite keeps no offset.
    assert isinstance(stored, str)
    assert stored.endswith("Z") is False and "+" not in stored

    with session_factory() as session:
        loaded = session.get(Job, job_id)
        assert loaded is not None
        assert loaded.captured_at.tzinfo is not None
        assert loaded.captured_at.utcoffset() == timedelta(0)


def test_a_naive_timestamp_is_refused(db: tuple[Engine, sessionmaker[Session]]) -> None:
    _, session_factory = db

    with session_factory() as session, pytest.raises(StatementError, match="naive datetime"):
        session.add(
            Job(platform="boss", title="Backend engineer", captured_at=datetime(2026, 1, 1))
        )
        session.commit()


def test_database_rejects_an_unknown_status(db: tuple[Engine, sessionmaker[Session]]) -> None:
    engine, session_factory = db

    with session_factory() as session:
        session.add(Job(platform="boss", title="Backend engineer"))
        session.commit()

    with engine.connect() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO application (job_id, status, created_at, updated_at) "
                "VALUES (1, 'ghosted-by-hand', '2026-01-01', '2026-01-01')"
            )
        )
        connection.commit()
