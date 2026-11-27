"""Serve the built single-page app from the API process.

One process, one port: the container runs exactly what `make dev` runs,
minus the Vite server. The mount is skipped when the build is absent, so a
backend-only checkout still works.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_spa(app: FastAPI, dist_dir: Path) -> None:
    """Serve ``dist_dir`` with an index.html fallback for client routes."""
    if not dist_dir.is_dir():
        return

    root = dist_dir.resolve()
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str) -> FileResponse:
        # An unknown /api path is a missing endpoint, not a page.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)

        candidate = (root / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)
