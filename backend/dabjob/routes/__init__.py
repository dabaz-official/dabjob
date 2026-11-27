"""HTTP routes. One module per surface."""

from __future__ import annotations

from . import applications, health, ingest, jobs

__all__ = ["applications", "health", "ingest", "jobs"]
