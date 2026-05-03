"""UTC timestamps on program records (date_added / date_updated)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def program_timestamp_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp_new_program_dates(program: dict[str, Any]) -> None:
    """Set both timestamps (e.g. new skeleton or first-time insert)."""
    t = program_timestamp_iso_utc()
    program["date_added"] = t
    program["date_updated"] = t


def bump_date_updated(program: dict[str, Any]) -> None:
    program["date_updated"] = program_timestamp_iso_utc()


def index_most_recently_added_program(programs: list[Any]) -> int | None:
    """
    Index of the program considered "last added".

    Prefer the row with the lexicographically greatest non-empty ``date_added``
    (ISO timestamps sort correctly). Ties break toward a larger array index.
    If no row has ``date_added``, fall back to the last index in the array.
    """
    if not programs:
        return None
    best: tuple[str, int] | None = None
    for i, p in enumerate(programs):
        if not isinstance(p, dict):
            continue
        da = p.get("date_added")
        if isinstance(da, str) and da.strip():
            key = (da.strip(), i)
            if best is None or key > best:
                best = key
    if best is not None:
        return best[1]
    return len(programs) - 1
