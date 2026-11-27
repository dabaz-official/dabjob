"""What version of each adapter the server is willing to accept.

A bookmarklet outlives a release. When an adapter's output changes shape, the
old bookmark keeps posting the old shape, and the failure is silent unless
something checks. This is that check: it is not security, it is freshness,
so a missing or unreadable registry allows everything rather than locking
the user out of their own tool.
"""

from __future__ import annotations

import json
from pathlib import Path


def required_version(registry_path: Path, adapter: str) -> int | None:
    """The minimum version for a known adapter, or None when unknown."""
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    adapters = payload.get("adapters")
    if not isinstance(adapters, dict):
        return None

    entry = adapters.get(adapter)
    if not isinstance(entry, dict):
        return None

    version = entry.get("min_version")
    return version if isinstance(version, int) else None
