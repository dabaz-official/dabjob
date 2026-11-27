from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dabjob.importers.aijobsearch import import_workspace
from dabjob.models import Application, Job, PipelineStatus

WORKSPACE = Path(__file__).parent / "fixtures" / "aijobsearch"


def _count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_tracker_rows_become_jobs_and_applications(session: Session) -> None:
    result = import_workspace(session, WORKSPACE)

    # Four tracker rows, plus two scraped postings that are not in the tracker.
    assert result.accepted == 6
    assert result.applications == 4
    # One scraped entry duplicates a tracker row by company+title.
    assert result.duplicates == 1
    assert result.failed == 0
    assert _count(session, Job) == 6
    assert _count(session, Application) == 4


def test_statuses_are_mapped_not_guessed(session: Session) -> None:
    import_workspace(session, WORKSPACE)

    statuses = sorted(
        {application.status for application in session.scalars(select(Application))},
        key=lambda item: item.value,
    )

    assert statuses == [
        PipelineStatus.APPLIED,
        PipelineStatus.GHOSTED,
        PipelineStatus.INTERVIEW,
        PipelineStatus.REJECTED,
    ]


def test_unreachable_entries_are_skipped(session: Session) -> None:
    """An entry that could not be fetched has nothing to import."""
    import_workspace(session, WORKSPACE)

    titles = set(session.scalars(select(Job.title)).all())

    # The fixture's unreachable entry is the only English "Platform Engineer";
    # the tracker's Chinese 平台工程师 is a different posting.
    assert "Platform Engineer" not in titles
    assert "平台工程师" in titles


def test_expired_entries_are_kept(session: Session) -> None:
    import_workspace(session, WORKSPACE)

    titles = set(session.scalars(select(Job.title)).all())

    assert "Data Analyst" in titles


def test_importing_twice_adds_nothing(session: Session) -> None:
    import_workspace(session, WORKSPACE)

    second = import_workspace(session, WORKSPACE)

    assert second.accepted == 0
    assert second.applications == 0
    assert second.duplicates == 7
    assert _count(session, Job) == 6
    assert _count(session, Application) == 4


def test_the_application_date_is_kept(session: Session) -> None:
    import_workspace(session, WORKSPACE)

    application = session.scalars(
        select(Application).join(Job).where(Job.title == "后端开发工程师")
    ).one()

    assert application.created_at.year == 2026
    assert application.created_at.month == 3
    assert application.created_at.day == 2


def test_an_unknown_tracker_status_fails_only_that_row(session: Session, tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "job_search_tracker.csv").write_text(
        "role,company,status\nBackend,Acme,applied\nFrontend,Acme,teleported\n",
        encoding="utf-8",
    )

    result = import_workspace(session, workspace)

    assert (result.accepted, result.failed) == (1, 1)
    assert result.errors[0].error.startswith("unknown_status:")


def test_invisible_characters_are_removed(session: Session, tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "job_search_tracker.csv").write_text(
        "role,company,status\n后\u200b端工程师,Acme,applied\n",
        encoding="utf-8",
    )

    import_workspace(session, workspace)

    assert session.scalars(select(Job.title)).one() == "后端工程师"


def test_a_directory_without_state_is_an_error(session: Session, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="ai-job-search workspace"):
        import_workspace(session, tmp_path)


def test_a_corrupt_seen_file_is_an_error(session: Session, tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    (workspace / "job_scraper").mkdir(parents=True)
    (workspace / "job_scraper" / "seen_jobs.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        import_workspace(session, workspace)
