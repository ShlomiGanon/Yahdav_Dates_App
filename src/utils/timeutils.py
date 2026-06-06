"""Time helpers shared across the persistence layer."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Current UTC time as a NAIVE `datetime` (no tzinfo).

    A drop-in replacement for the deprecated `datetime.utcnow()` (slated for
    removal in CPython) that produces the IDENTICAL value and ISO format — so
    every ISO timestamp already persisted in SQLite, and the lexical /
    `datetime.fromisoformat` comparisons that read them, keep working unchanged.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
