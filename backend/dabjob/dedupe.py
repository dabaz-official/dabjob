"""One identity per posting.

The rule from the roadmap: use the platform's own id when there is one, and
fall back to the company, title and city a human would compare when there is
not. The fingerprint is what makes an import idempotent.
"""

from __future__ import annotations

import hashlib
import re

_WHITESPACE = re.compile(r"\s+")


def _normalise(value: str | None) -> str:
    if not value:
        return ""
    return _WHITESPACE.sub(" ", value).strip().casefold()


def fingerprint(
    platform: str,
    external_id: str | None,
    company: str | None,
    title: str | None,
    city: str | None,
) -> str:
    if external_id:
        basis = f"{_normalise(platform)}|{_normalise(external_id)}"
    else:
        basis = "|".join(_normalise(part) for part in (company, title, city))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
