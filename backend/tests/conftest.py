"""Shared fixtures.

``api`` gives a running app on a database migrated the same way a user's is:
through Alembic, not through ``metadata.create_all``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alembic import command
from dabjob.config import Settings
from dabjob.main import create_app

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def api(tmp_path: Path) -> Iterator[tuple[TestClient, FastAPI]]:
    settings = Settings(
        data_dir=tmp_path,
        host="127.0.0.1",
        allow_remote=False,
        static_dir=tmp_path / "no-build",
    )
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")

    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client, app
