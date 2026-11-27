from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alembic import command
from dabjob.config import Settings
from dabjob.db import build_engine, build_sessionmaker
from dabjob.demo import DEMO_JOBS, seed
from dabjob.models import Job

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    settings = Settings(
        data_dir=tmp_path, host="127.0.0.1", allow_remote=False, static_dir=tmp_path / "no-build"
    )
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")

    engine = build_engine(settings)
    with build_sessionmaker(engine)() as session:
        yield session
    engine.dispose()


def test_the_dataset_is_five_postings() -> None:
    assert len(DEMO_JOBS) == 5


def test_seeding_inserts_five(db_session: Session) -> None:
    assert seed(db_session) == 5
    assert db_session.scalar(select(func.count()).select_from(Job)) == 5


def test_seeding_twice_inserts_nothing(db_session: Session) -> None:
    seed(db_session)

    assert seed(db_session) == 0
    assert db_session.scalar(select(func.count()).select_from(Job)) == 5


def test_the_demo_data_is_searchable_by_the_index(db_session: Session) -> None:
    seed(db_session)

    rows = db_session.execute(
        select(Job.title).where(Job.id.in_(select(Job.id).where(Job.jd_text.like("%FastAPI%"))))
    ).all()

    assert [row.title for row in rows] == ["后端开发工程师"]
