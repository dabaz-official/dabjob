"""Importers from other job-search tools.

One module per tool. Each reads only formats the other tool documents as its
own state, ships a fixture snapshot in the tests, and never becomes
load-bearing: if the format changes, the importer fails loudly and the rest
of the application is unaffected.
"""

from __future__ import annotations

__all__: list[str] = []
