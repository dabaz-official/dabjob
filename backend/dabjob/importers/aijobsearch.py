"""Read an `ai-job-search` workspace.

Two files, both documented by that project:

* ``job_search_tracker.csv`` — the application tracker, fourteen columns,
  statuses such as ``applied``, ``interview`` and ``no_response``;
* ``job_scraper/seen_jobs.json`` — scrape history, either a bare object or
  ``{"seen": {...}}`` keyed by a company+title slug, with ``scored`` and
  ``expired`` entries.

A tracker row becomes a job plus an application. A scraped entry becomes a
job only: it is a candidate someone has not acted on. When the same posting
appears in both, the company+title fingerprint keeps one row.

Run with ``make import DIR=/path/to/ai-job-search``.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dedupe import fingerprint
from ..gate import inspect
from ..models import (
    Application,
    IngestItem,
    IngestOutcome,
    IngestRun,
    IngestSource,
    IngestStatus,
    Job,
    PipelineStatus,
)

ADAPTER = "ai-job-search"
TRACKER_FILE = "job_search_tracker.csv"
SEEN_FILE = Path("job_scraper") / "seen_jobs.json"

TRACKER_STATUS: dict[str, PipelineStatus] = {
    "drafted": PipelineStatus.SAVED,
    "applied": PipelineStatus.APPLIED,
    "interview": PipelineStatus.INTERVIEW,
    "offer": PipelineStatus.OFFER,
    "hired": PipelineStatus.OFFER,
    "rejected": PipelineStatus.REJECTED,
    "no_response": PipelineStatus.GHOSTED,
    "no response": PipelineStatus.GHOSTED,
    "offer_declined": PipelineStatus.DROPPED,
    "offer declined": PipelineStatus.DROPPED,
    "withdrawn": PipelineStatus.DROPPED,
}

SEEN_STATUSES = frozenset({"scored", "expired", ""})


@dataclass(frozen=True)
class RowError:
    source: str
    row: str
    error: str


@dataclass
class ImportResult:
    run_id: int = 0
    accepted: int = 0
    duplicates: int = 0
    failed: int = 0
    applications: int = 0
    errors: list[RowError] = field(default_factory=list)


def import_workspace(session: Session, root: Path) -> ImportResult:
    tracker = root / TRACKER_FILE
    seen = root / SEEN_FILE
    if not tracker.is_file() and not seen.is_file():
        raise FileNotFoundError(
            f"neither {tracker} nor {seen} exists — is {root} an ai-job-search workspace?"
        )

    result = ImportResult()
    run = IngestRun(source=IngestSource.IMPORTER, adapter=ADAPTER, status=IngestStatus.COMPLETED)
    session.add(run)
    session.flush()
    result.run_id = run.id

    if tracker.is_file():
        _import_tracker(session, run, result, tracker)
    if seen.is_file():
        _import_seen(session, run, result, seen)

    run.accepted = result.accepted
    run.duplicates = result.duplicates
    run.failed = result.failed
    session.commit()
    return result


def _import_tracker(session: Session, run: IngestRun, result: ImportResult, path: Path) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=2):
            _tracker_row(session, run, result, row, number)


def _tracker_row(
    session: Session, run: IngestRun, result: ImportResult, row: dict[str, str], number: int
) -> None:
    title, flags = _gated(row.get("role"))
    company, company_flags = _gated(row.get("company"))
    flags += company_flags

    if not title:
        _fail(session, run, result, f"line {number}", "missing_role", row, flags)
        return

    status_text = (row.get("status") or "").strip().casefold()
    status = TRACKER_STATUS.get(status_text)
    if status is None:
        _fail(
            session,
            run,
            result,
            f"line {number}",
            f"unknown_status:{row.get('status')}",
            row,
            flags,
        )
        return

    job = _upsert_job(
        session,
        run,
        result,
        title=title,
        company=company,
        url=(row.get("source") or "").strip() or None,
        platform=(row.get("channel") or "").strip() or "ai-job-search",
        raw=row,
        flags=flags,
    )
    if job is None:
        return

    applied_at = _parse_date(row.get("date"))
    session.add(
        Application(
            job_id=job.id,
            status=status,
            channel=(row.get("channel") or "").strip() or None,
            **({"created_at": applied_at} if applied_at else {}),
        )
    )
    result.applications += 1


def _import_seen(session: Session, run: IngestRun, result: ImportResult, path: Path) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from error

    entries = (
        document.get("seen") if isinstance(document, dict) and "seen" in document else document
    )
    if not isinstance(entries, dict):
        raise ValueError(f"{path}: expected an object of job entries")

    for key, entry in entries.items():
        if not isinstance(entry, dict):
            _fail(session, run, result, str(key), "entry_is_not_an_object", {}, [])
            continue

        status = str(entry.get("status") or "").strip().casefold()
        if status not in SEEN_STATUSES:
            continue  # unreachable and similar carry nothing to import

        title, flags = _gated(entry.get("title"))
        company, company_flags = _gated(entry.get("company"))
        flags += company_flags
        if not title:
            _fail(session, run, result, str(key), "missing_title", entry, flags)
            continue

        _upsert_job(
            session,
            run,
            result,
            title=title,
            company=company,
            url=_text(entry.get("url")) or None,
            platform=_text(entry.get("portal")) or "ai-job-search",
            raw=entry,
            flags=flags,
        )


def _upsert_job(
    session: Session,
    run: IngestRun,
    result: ImportResult,
    *,
    title: str,
    company: str,
    url: str | None,
    platform: str,
    raw: dict[str, Any],
    flags: list[str],
) -> Job | None:
    marker = fingerprint(ADAPTER, None, company, title, None)
    if session.scalar(select(Job.id).where(Job.fingerprint == marker)) is not None:
        result.duplicates += 1
        session.add(
            IngestItem(
                run_id=run.id,
                url=url,
                outcome=IngestOutcome.DUPLICATE,
                raw_payload=raw,
                gate_flags=flags,
            )
        )
        return None

    job = Job(
        platform=platform,
        url=url,
        title=title,
        company_name=company,
        jd_text="",
        fingerprint=marker,
    )
    session.add(job)
    session.flush()

    session.add(
        IngestItem(
            run_id=run.id,
            url=url,
            outcome=IngestOutcome.ACCEPTED,
            raw_payload=raw,
            gate_flags=flags,
        )
    )
    result.accepted += 1
    return job


def _fail(
    session: Session,
    run: IngestRun,
    result: ImportResult,
    where: str,
    error: str,
    raw: dict[str, Any],
    flags: list[str],
) -> None:
    result.failed += 1
    if len(result.errors) < 20:
        result.errors.append(RowError(source=ADAPTER, row=where, error=error))
    session.add(
        IngestItem(
            run_id=run.id,
            outcome=IngestOutcome.FAILED,
            raw_payload=raw,
            gate_flags=flags,
            error=error,
        )
    )


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _gated(value: Any) -> tuple[str, list[str]]:
    gated = inspect(_text(value))
    return gated.text, list(gated.flags)


def _parse_date(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(text, pattern)
        except ValueError:
            continue
        return parsed.replace(tzinfo=UTC)
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m dabjob.importers.aijobsearch DIR", file=sys.stderr)
        return 2

    from ..config import Settings
    from ..db import build_engine, build_sessionmaker

    root = Path(sys.argv[1])
    engine = build_engine(Settings())
    try:
        with build_sessionmaker(engine)() as session:
            result = import_workspace(session, root)
    except (FileNotFoundError, ValueError) as error:
        print(f"import: {error}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(
        f"jobs={result.accepted} applications={result.applications} "
        f"duplicates={result.duplicates} failed={result.failed}"
    )
    for item in result.errors:
        print(f"  {item.row}: {item.error}", file=sys.stderr)
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
