"""HTTP routes. One module per surface."""

from __future__ import annotations

from . import applications, browser_ingest, health, ingest, jobs, profile

__all__ = ["applications", "browser_ingest", "health", "ingest", "jobs", "profile"]
