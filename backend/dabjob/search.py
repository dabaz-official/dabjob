"""Search over postings.

FTS5 with the trigram tokenizer matches substrings, which is what a search
box is expected to do with Chinese text: `unicode61` turns a run of Chinese
characters into one token, so "开发" would find nothing inside
"后端开发工程师".

The cost is that trigram needs three characters, so shorter queries fall
back to LIKE. A two-character Chinese query is common enough that returning
silence would look like a bug.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from .models import Job

MIN_TRIGRAM_QUERY = 3

SNIPPET_START = "<mark>"
SNIPPET_END = "</mark>"
SNIPPET_ELLIPSIS = "…"


@dataclass(frozen=True)
class JobHit:
    job: Job
    snippet: str | None


def _fts_query(raw: str) -> str:
    """Quote the input so FTS5 operators in user text are treated as text."""
    return '"' + raw.replace('"', '""') + '"'


def search_jobs(session: Session, query: str, limit: int = 50) -> list[JobHit]:
    cleaned = query.strip()
    if not cleaned:
        return []
    if len(cleaned) < MIN_TRIGRAM_QUERY:
        return _search_like(session, cleaned, limit)
    return _search_fts(session, cleaned, limit)


def _search_fts(session: Session, query: str, limit: int) -> list[JobHit]:
    rows = session.execute(
        text(
            """
            SELECT job_fts.rowid AS id,
                   snippet(job_fts, -1, :start, :end, :ellipsis, 12) AS excerpt
            FROM job_fts
            WHERE job_fts MATCH :match
            ORDER BY rank
            LIMIT :limit
            """
        ),
        {
            "match": _fts_query(query),
            "start": SNIPPET_START,
            "end": SNIPPET_END,
            "ellipsis": SNIPPET_ELLIPSIS,
            "limit": limit,
        },
    ).all()

    if not rows:
        return []

    ids = [row.id for row in rows]
    jobs = {job.id: job for job in session.scalars(select(Job).where(Job.id.in_(ids)))}
    return [JobHit(job=jobs[row.id], snippet=row.excerpt) for row in rows if row.id in jobs]


def _search_like(session: Session, query: str, limit: int) -> list[JobHit]:
    pattern = f"%{query}%"
    statement = (
        select(Job)
        .where(
            or_(
                Job.title.ilike(pattern),
                Job.company_name.ilike(pattern),
                Job.jd_text.ilike(pattern),
            )
        )
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    return [JobHit(job=job, snippet=None) for job in session.scalars(statement)]
