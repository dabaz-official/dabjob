"""The browser ingest endpoint.

This is the most exposed surface in the project: it is reachable from a page
the user is browsing, so it carries three independent guards.

* a token, from `DABJOB_TOKEN`, compared in constant time;
* an Origin allow-list, because a token in a bookmarklet is visible to
  anything that can read the address bar;
* a body size cap, because the endpoint parses whatever it is handed.

Two details exist to avoid a CORS preflight entirely: the body may be
`text/plain`, and the token may travel in the query string. A preflight is a
second request that a local-network guard can block, and a bookmarklet that
works on one browser and silently fails on another is worse than a slightly
uglier URL.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..capture_registry import required_version
from ..dedupe import fingerprint
from ..deps import get_session
from ..gate import inspect
from ..models import (
    IngestItem,
    IngestOutcome,
    IngestRun,
    IngestSource,
    IngestStatus,
    Job,
)
from ..schemas import CaptureBatch, CaptureResult

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

SessionDep = Annotated[Session, Depends(get_session)]

MAX_BODY_BYTES = 256 * 1024
# A page snapshot is a debugging aid, not an ingest: 2 MB fits a BOSS list page.
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024


@router.post("/browser")
async def ingest_browser(
    request: Request, session: SessionDep, token: str | None = None
) -> Response:
    settings = request.app.state.settings
    origin = request.headers.get("origin")

    _check_enabled(settings.token, settings.origin_allowlist)
    _check_origin(origin, settings.origin_allowlist)
    _check_token(settings.token, token, request)

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload is larger than 256 KB")

    try:
        payload = CaptureBatch.model_validate(json.loads(body.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail=f"body is not JSON: {error}") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    _check_adapter_version(settings.capture_registry, payload)

    result = _store(session, payload)

    response = Response(
        content=result.model_dump_json(),
        media_type="application/json",
    )
    if origin:
        response.headers["access-control-allow-origin"] = origin
        response.headers["vary"] = "origin"
    return response


@router.post("/snapshot")
async def capture_snapshot(
    request: Request, token: str | None = None, adapter: str = "page"
) -> Response:
    """Save the page's current HTML under data/snapshots/.

    This exists because a site may hide its rendered DOM from everything but
    the page itself: BOSS reloads when Developer Tools opens, so "Copy
    outerHTML" is not an option. A bookmarklet runs inside the page and is
    not detected, which makes this the only reliable way to obtain a real DOM
    to write an adapter against.
    """
    settings = request.app.state.settings
    origin = request.headers.get("origin")

    _check_enabled(settings.token, settings.origin_allowlist)
    _check_origin(origin, settings.origin_allowlist)
    _check_token(settings.token, token, request)

    body = await request.body()
    if len(body) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(status_code=413, detail="snapshot is larger than 2 MB")
    if not body.strip():
        raise HTTPException(status_code=400, detail="empty snapshot")

    directory = settings.data_dir / "snapshots"
    directory.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_adapter = re.sub(r"[^a-z0-9-]", "", adapter.lower())[:40] or "page"
    path = directory / f"{stamp}-{safe_adapter}.html"
    path.write_bytes(body)

    response = Response(
        content=json.dumps({"file": str(path), "bytes": len(body)}, ensure_ascii=False),
        media_type="application/json",
    )
    if origin:
        response.headers["access-control-allow-origin"] = origin
        response.headers["vary"] = "origin"
    return response


@router.options("/browser")
def ingest_browser_preflight(request: Request) -> Response:
    """Answer a preflight for the allowed origins, and nobody else.

    The bookmarklet avoids preflighting, but a future extension will not, and
    a blocked OPTIONS is a confusing failure mode.
    """
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    if not origin or origin.rstrip("/").lower() not in settings.origin_allowlist:
        raise HTTPException(status_code=403, detail="origin is not allowed")

    return Response(
        status_code=204,
        headers={
            "access-control-allow-origin": origin,
            "access-control-allow-methods": "POST, OPTIONS",
            "access-control-allow-headers": "content-type, x-dabjob-token",
            "access-control-max-age": "600",
            "vary": "origin",
        },
    )


def _check_adapter_version(registry: Path, payload: CaptureBatch) -> None:
    minimum = required_version(registry, payload.adapter)
    if minimum is not None and payload.adapter_version < minimum:
        raise HTTPException(
            status_code=409,
            detail=(
                f"adapter {payload.adapter!r} is version {payload.adapter_version}, "
                f"but this server needs at least {minimum}. "
                "Rebuild the bookmarklet with `make bookmarklet` and replace its URL."
            ),
        )


def _check_enabled(token: str | None, allowlist: tuple[str, ...]) -> None:
    if not token:
        raise HTTPException(
            status_code=503,
            detail="browser ingest is disabled: set DABJOB_TOKEN in .env",
        )
    if not allowlist:
        raise HTTPException(
            status_code=503,
            detail="browser ingest is disabled: set DABJOB_ALLOWED_ORIGINS in .env",
        )


def _check_origin(origin: str | None, allowlist: tuple[str, ...]) -> None:
    if origin is None:
        return  # a CLI probe, not a browser; the token is still required
    if origin.rstrip("/").lower() not in allowlist:
        raise HTTPException(status_code=403, detail=f"origin {origin!r} is not allowed")


def _check_token(expected: str | None, query_token: str | None, request: Request) -> None:
    presented = request.headers.get("x-dabjob-token") or query_token
    if not presented or not expected or not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="missing or invalid token")


def _store(session: Session, payload: CaptureBatch) -> CaptureResult:
    run = IngestRun(
        source=IngestSource.BOOKMARKLET,
        adapter=f"{payload.adapter}@{payload.adapter_version}",
        status=IngestStatus.COMPLETED,
    )
    session.add(run)
    session.flush()

    result = CaptureResult(run_id=run.id, accepted=0, duplicates=0, failed=0)

    for item in payload.items:
        title = inspect(item.title)
        company = inspect(item.company or "")
        jd = inspect(item.jd_text)
        flags = [*title.flags, *company.flags, *jd.flags]

        if not title.text.strip():
            result.failed += 1
            if len(result.errors) < 20:
                result.errors.append(f"{item.title!r}: empty title after the gate")
            session.add(
                IngestItem(
                    run_id=run.id,
                    url=item.url,
                    outcome=IngestOutcome.FAILED,
                    raw_payload=item.model_dump(),
                    gate_flags=flags,
                    error="empty_title",
                )
            )
            continue

        marker = fingerprint(item.platform, item.external_id, company.text, title.text, item.city)
        if session.scalar(select(Job.id).where(Job.fingerprint == marker)) is not None:
            result.duplicates += 1
            session.add(
                IngestItem(
                    run_id=run.id,
                    url=item.url,
                    outcome=IngestOutcome.DUPLICATE,
                    raw_payload=item.model_dump(),
                    gate_flags=flags,
                )
            )
            continue

        session.add(
            Job(
                platform=item.platform,
                external_id=item.external_id,
                url=item.url,
                title=title.text,
                company_name=company.text,
                city=item.city,
                salary_text=item.salary_text,
                seniority=item.seniority,
                jd_text=jd.text,
                fingerprint=marker,
            )
        )
        session.add(
            IngestItem(
                run_id=run.id,
                url=item.url,
                outcome=IngestOutcome.ACCEPTED,
                raw_payload=item.model_dump(),
                gate_flags=flags,
            )
        )
        result.accepted += 1

    run.accepted = result.accepted
    run.duplicates = result.duplicates
    run.failed = result.failed
    session.commit()
    return result
