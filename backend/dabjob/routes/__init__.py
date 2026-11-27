"""HTTP routes. One module per surface."""

from __future__ import annotations

from . import health, ingest, jobs

__all__ = ["health", "ingest", "jobs"]
