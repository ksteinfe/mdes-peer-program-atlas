"""Locate repository root (directory containing corpus/programs.json)."""

from __future__ import annotations

import pathlib
from functools import lru_cache


def find_repo_root(start: pathlib.Path | None = None) -> pathlib.Path:
    cur = (start or pathlib.Path.cwd()).resolve()
    for _ in range(32):
        candidate = cur / "corpus" / "programs.json"
        if candidate.is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    raise FileNotFoundError(
        "Could not find corpus/programs.json in current or parent directories."
    )


@lru_cache(maxsize=1)
def cached_repo_root() -> pathlib.Path:
    return find_repo_root()
