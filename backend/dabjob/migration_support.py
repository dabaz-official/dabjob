"""Helpers shared by Alembic and the schema tests.

`alembic revision --autogenerate` compares the database to the metadata. It
cannot see a virtual table, so without this filter every future revision
would contain a `DROP TABLE job_fts` — quietly deleting the search index on
the next upgrade.
"""

from __future__ import annotations

from typing import Any

# The FTS5 table plus the shadow tables SQLite creates beside it.
FTS_PREFIX = "job_fts"


def include_object(
    obj: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Return False for objects Alembic must never generate DDL for."""
    is_fts_table = type_ == "table" and name is not None and name.startswith(FTS_PREFIX)
    return not is_fts_table
