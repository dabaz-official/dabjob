"""Shared fixtures.

Both fixtures run the real Alembic migrations rather than
``metadata.create_all``, so the FTS table and its triggers exist exactly as
a user's database has them.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from alembic import command
from dabjob.config import Settings
from dabjob.db import build_engine, build_sessionmaker
from dabjob.main import create_app

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        host="127.0.0.1",
        allow_remote=False,
        static_dir=tmp_path / "no-build",
    )


def _migrate(settings: Settings) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    settings = _settings(tmp_path)
    _migrate(settings)

    engine = build_engine(settings)
    with build_sessionmaker(engine)() as db_session:
        yield db_session
    engine.dispose()


@pytest.fixture
def api(tmp_path: Path) -> Iterator[tuple[TestClient, FastAPI]]:
    settings = _settings(tmp_path)
    _migrate(settings)

    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client, app
