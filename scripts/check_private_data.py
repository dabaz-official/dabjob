#!/usr/bin/env python3
"""Fail the build when private data looks committed.

This is a guard, not a proof. It catches the mistakes that are actually
easy to make — a database file, a stray .env, a real mobile number pasted
into a fixture — and stays quiet about everything else. Invented fixtures
are expected; real ones are not.

Rules come from GOVERNANCE.md ("Data and privacy") and ROADMAP.md §8.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PATHS = (
    (re.compile(r"^data/"), "the database directory is never tracked"),
    (re.compile(r"(^|/)\.env$"), "a real environment file is never tracked"),
    (re.compile(r"(^|/)\.env\.(?!example$)"), "a real environment file is never tracked"),
    (re.compile(r"\.(db|db-wal|db-shm|sqlite|sqlite3)$"), "a database file is never tracked"),
)

PATTERNS = (
    ("mainland mobile number", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("resident id number", re.compile(r"(?<!\d)\d{14}\d{3}[\dXx](?!\d)")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

# Binary or generated files: a long digit run in a lockfile is a hash, not a
# phone number, and scanning megabytes of JSON slows CI for no benefit.
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf",
    ".pdf", ".zip", ".gz", ".lock",
}
SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}


def tracked_files() -> list[str]:
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("check_private_data: not a git checkout, skipping", file=sys.stderr)
        return []
    return [name for name in output.split("\0") if name]


def main() -> int:
    findings: list[str] = []

    for name in tracked_files():
        for pattern, reason in FORBIDDEN_PATHS:
            if pattern.search(name):
                findings.append(f"{name}: tracked, but {reason}")
                break

        path = Path(name)
        if path.suffix in SKIP_SUFFIXES or path.name in SKIP_NAMES:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS:
                match = pattern.search(line)
                if match:
                    findings.append(f"{name}:{line_number}: looks like a {label}")

    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} finding(s). See GOVERNANCE.md, 'Data and privacy'.")
        return 1
    print("check_private_data: no committed private data found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
