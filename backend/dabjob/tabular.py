"""Tabular ingest: a spreadsheet is where most people already keep this data.

Two shapes are accepted, because a user copy-pastes whichever they have: a
CSV (comma, semicolon or tab) and a JSON array of objects.

Column names are guessed from a synonym list, but the guess is only a
starting point — the import takes an explicit mapping, so a wrong guess is
visible and correctable rather than silent.

Every row goes through the integrity gate like any other ingest path, and
each row that lands creates both a job and an application: a row in a job
tracker is a job someone already acted on.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .dedupe import fingerprint
from .gate import inspect
from .models import (
    Application,
    IngestItem,
    IngestOutcome,
    IngestRun,
    IngestSource,
    IngestStatus,
    Job,
    PipelineStatus,
)

FIELD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "title": ("岗位", "职位", "岗位名称", "职位名称", "title", "job title", "position", "role"),
    "company": ("公司", "公司名称", "企业", "company", "employer"),
    "city": ("城市", "地点", "工作地点", "地区", "city", "location"),
    "salary": ("薪资", "薪水", "待遇", "薪资范围", "salary", "pay", "compensation"),
    "status": ("状态", "进展", "进度", "status", "stage", "state"),
    "url": ("链接", "网址", "url", "link", "job url"),
}

STATUS_SYNONYMS: dict[str, PipelineStatus] = {
    "saved": PipelineStatus.SAVED,
    "收藏": PipelineStatus.SAVED,
    "待投": PipelineStatus.SAVED,
    "wishlist": PipelineStatus.SAVED,
    "applied": PipelineStatus.APPLIED,
    "已投递": PipelineStatus.APPLIED,
    "已申请": PipelineStatus.APPLIED,
    "投递": PipelineStatus.APPLIED,
    "chatted": PipelineStatus.CHATTED,
    "沟通中": PipelineStatus.CHATTED,
    "已沟通": PipelineStatus.CHATTED,
    "screening": PipelineStatus.SCREENING,
    "筛选中": PipelineStatus.SCREENING,
    "简历筛选": PipelineStatus.SCREENING,
    "interview": PipelineStatus.INTERVIEW,
    "面试": PipelineStatus.INTERVIEW,
    "面试中": PipelineStatus.INTERVIEW,
    "offer": PipelineStatus.OFFER,
    "录用": PipelineStatus.OFFER,
    "已录用": PipelineStatus.OFFER,
    "rejected": PipelineStatus.REJECTED,
    "拒绝": PipelineStatus.REJECTED,
    "已拒": PipelineStatus.REJECTED,
    "不合适": PipelineStatus.REJECTED,
    "ghosted": PipelineStatus.GHOSTED,
    "已读不回": PipelineStatus.GHOSTED,
    "失联": PipelineStatus.GHOSTED,
    "dropped": PipelineStatus.DROPPED,
    "放弃": PipelineStatus.DROPPED,
}

MAX_ROWS = 2000
_PUNCTUATION = re.compile(r"[\s_\-/]+")


@dataclass(frozen=True)
class Table:
    headers: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class RowError:
    row: int
    error: str


@dataclass
class ImportOutcome:
    run_id: int = 0
    accepted: int = 0
    duplicates: int = 0
    failed: int = 0
    errors: list[RowError] = field(default_factory=list)


def _normalise_header(value: str) -> str:
    return _PUNCTUATION.sub("", value.strip().casefold())


def read_table(text: str) -> Table:
    stripped = text.lstrip("\ufeff").strip()
    if not stripped:
        raise ValueError("empty input")

    if stripped[0] in "[{":
        return _read_json(stripped)
    return _read_csv(stripped)


def _read_json(text: str) -> Table:
    payload = json.loads(text)
    if isinstance(payload, dict):
        rows: list[dict[str, Any]] = [payload]
    elif isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    else:
        raise ValueError("expected a JSON object or an array of objects")

    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(str(key))

    if not headers:
        raise ValueError("expected a JSON object or an array of objects")

    return Table(
        headers=tuple(headers),
        rows=tuple({header: _stringify(row.get(header)) for header in headers} for row in rows),
    )


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _read_csv(text: str) -> Table:
    sample = text[:4096]
    try:
        dialect: Any = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = tuple(header.strip() for header in (reader.fieldnames or ()))
    rows = tuple(
        {
            (key or "").strip(): (value or "").strip()
            for key, value in row.items()
            if key is not None
        }
        for row in reader
    )
    return Table(headers=headers, rows=rows)


def suggest_mapping(headers: tuple[str, ...]) -> dict[str, str | None]:
    normalised = {_normalise_header(header): header for header in headers}
    mapping: dict[str, str | None] = {}
    for target, synonyms in FIELD_SYNONYMS.items():
        mapping[target] = None
        for synonym in synonyms:
            match = normalised.get(_normalise_header(synonym))
            if match is not None:
                mapping[target] = match
                break
    return mapping


def parse_status(value: str) -> PipelineStatus | None:
    if not value.strip():
        return None
    return STATUS_SYNONYMS.get(_normalise_header(value))


def import_rows(
    session: Session,
    table: Table,
    mapping: dict[str, str | None],
    platform: str = "csv",
) -> ImportOutcome:
    outcome = ImportOutcome()

    run = IngestRun(source=IngestSource.TABULAR, adapter=platform, status=IngestStatus.COMPLETED)
    session.add(run)
    session.flush()
    outcome.run_id = run.id

    for index, row in enumerate(table.rows, start=1):
        if index > MAX_ROWS:
            outcome.failed += 1
            outcome.errors.append(RowError(row=index, error="row_limit_exceeded"))
            continue
        _import_row(session, run, outcome, row, mapping, index, platform)

    run.accepted = outcome.accepted
    run.duplicates = outcome.duplicates
    run.failed = outcome.failed
    session.commit()
    return outcome


def _import_row(
    session: Session,
    run: IngestRun,
    outcome: ImportOutcome,
    row: dict[str, str],
    mapping: dict[str, str | None],
    index: int,
    platform: str,
) -> None:
    values: dict[str, str] = {}
    flags: list[str] = []
    for target, header in mapping.items():
        raw = row.get(header, "") if header else ""
        gated = inspect(raw)
        flags.extend(gated.flags)
        values[target] = gated.text

    title = values.get("title", "").strip()
    if not title:
        _fail(session, run, outcome, row, index, "missing_title", flags)
        return

    status_text = values.get("status", "").strip()
    status = parse_status(status_text)
    if status_text and status is None:
        _fail(session, run, outcome, row, index, f"unknown_status:{status_text}", flags)
        return
    if status is None:
        status = PipelineStatus.APPLIED

    company = values.get("company", "").strip() or None
    city = values.get("city", "").strip() or None
    marker = fingerprint(platform, None, company, title, city)

    if session.scalar(select(Job.id).where(Job.fingerprint == marker)) is not None:
        outcome.duplicates += 1
        session.add(
            IngestItem(
                run_id=run.id,
                url=values.get("url") or None,
                outcome=IngestOutcome.DUPLICATE,
                raw_payload=row,
                gate_flags=flags,
            )
        )
        return

    job = Job(
        platform=platform,
        url=values.get("url") or None,
        title=title,
        company_name=company or "",
        city=city,
        salary_text=values.get("salary") or None,
        jd_text="",
        fingerprint=marker,
    )
    session.add(job)
    session.flush()

    session.add(Application(job_id=job.id, status=status, channel=platform))
    session.add(
        IngestItem(
            run_id=run.id,
            url=values.get("url") or None,
            outcome=IngestOutcome.ACCEPTED,
            raw_payload=row,
            gate_flags=flags,
        )
    )
    outcome.accepted += 1


def _fail(
    session: Session,
    run: IngestRun,
    outcome: ImportOutcome,
    row: dict[str, str],
    index: int,
    error: str,
    flags: list[str],
) -> None:
    outcome.failed += 1
    if len(outcome.errors) < 20:
        outcome.errors.append(RowError(row=index, error=error))
    session.add(
        IngestItem(
            run_id=run.id,
            outcome=IngestOutcome.FAILED,
            raw_payload=row,
            gate_flags=flags,
            error=error,
        )
    )


def main() -> int:
    """Import a file from the command line: ``python -m dabjob.tabular FILE``."""
    if len(sys.argv) < 2:
        print("usage: python -m dabjob.tabular FILE", file=sys.stderr)
        return 2

    from .config import Settings
    from .db import build_engine, build_sessionmaker

    path = Path(sys.argv[1])
    table = read_table(path.read_text(encoding="utf-8-sig"))
    mapping = suggest_mapping(table.headers)

    print(f"{len(table.rows)} row(s), columns: {', '.join(table.headers)}")
    print("mapping: " + ", ".join(f"{k}<-{v}" for k, v in mapping.items() if v))

    engine = build_engine(Settings())
    try:
        with build_sessionmaker(engine)() as session:
            outcome = import_rows(session, table, mapping)
    finally:
        engine.dispose()

    print(f"accepted={outcome.accepted} duplicates={outcome.duplicates} failed={outcome.failed}")
    for item in outcome.errors:
        print(f"  row {item.row}: {item.error}", file=sys.stderr)
    return 0 if outcome.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
