"""Read/write corpus JSON with backup."""

from __future__ import annotations

import json
import pathlib
import shutil
from datetime import datetime, timezone
from typing import Any


def corpus_path(repo_root: pathlib.Path) -> pathlib.Path:
    return repo_root / "corpus" / "programs.json"


def backup_path(repo_root: pathlib.Path) -> pathlib.Path:
    return repo_root / "corpus" / "programs.backup.json"


def dated_corpus_archive_path(repo_root: pathlib.Path) -> pathlib.Path:
    """Path for a UTC timestamped copy of ``programs.json`` (filename-safe)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / "corpus" / f"programs.archive.{ts}.json"


def load_corpus(repo_root: pathlib.Path) -> dict[str, Any]:
    path = corpus_path(repo_root)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_corpus(repo_root: pathlib.Path, data: dict[str, Any]) -> None:
    path = corpus_path(repo_root)
    bpath = backup_path(repo_root)
    if path.is_file():
        shutil.copy2(path, bpath)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def programs_list(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    if "programs" not in corpus or not isinstance(corpus["programs"], list):
        raise ValueError("corpus must contain a 'programs' array")
    return corpus["programs"]


def program_by_id(corpus: dict[str, Any], program_id: str) -> dict[str, Any] | None:
    for p in programs_list(corpus):
        if p.get("program_id") == program_id:
            return p
    return None


def clear_all_programs(repo_root: pathlib.Path) -> tuple[int, pathlib.Path | None]:
    """
    Copy ``corpus/programs.json`` to a dated archive, then set ``programs`` to ``[]``.

    Returns ``(removed_count, archive_path)``. If there were no programs, does not
    create a dated archive and returns ``(0, None)``. ``write_corpus`` also copies
    the pre-write file to ``programs.backup.json``.
    """
    data = load_corpus(repo_root)
    programs = programs_list(data)
    n = len(programs)
    archive: pathlib.Path | None = None
    if n > 0:
        archive = dated_corpus_archive_path(repo_root)
        shutil.copy2(corpus_path(repo_root), archive)
    data["programs"] = []
    write_corpus(repo_root, data)
    return n, archive
