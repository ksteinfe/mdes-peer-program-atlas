#!/usr/bin/env python3
"""
Export ``curriculum.core_courses`` rows from ``corpus/programs.json``, one JSON file per
``primary_type``. Each file contains a JSON array of course objects exactly as stored in
the corpus (no program wrapper).

Usage (from repo root)::

  python tools/export_core_courses_by_primary_type.py
  python tools/export_core_courses_by_primary_type.py --out-dir export-output/my_export

Output files are named ``{primary_type}.json``. Rows with a missing or non-string
``primary_type`` are written to ``_missing_primary_type.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "corpus" / "programs.json").is_file():
            return p
    raise SystemExit(
        "Could not find corpus/programs.json. Run from the repo or pass --corpus explicitly."
    )


def safe_primary_type_filename(primary_type: str) -> str:
    """Map primary_type id to a single safe filename stem (Windows-safe)."""
    if primary_type == "_missing_primary_type":
        return "_missing_primary_type"
    if re.fullmatch(r"[A-Za-z0-9_]+", primary_type):
        return primary_type
    return re.sub(r"[^A-Za-z0-9_]+", "_", primary_type).strip("_") or "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to programs.json (default: <repo>/corpus/programs.json)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory (default: <repo>/export-output/core_courses_by_primary_type)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent (default: 2). Use 0 for compact JSON.",
    )
    args = parser.parse_args()

    repo = find_repo_root()
    corpus_path = args.corpus.resolve() if args.corpus else repo / "corpus" / "programs.json"
    out_dir = (
        args.out_dir.resolve()
        if args.out_dir
        else repo / "export-output" / "core_courses_by_primary_type"
    )

    if not corpus_path.is_file():
        raise SystemExit(f"Corpus not found: {corpus_path}")

    with corpus_path.open(encoding="utf-8") as f:
        data = json.load(f)

    programs = data.get("programs")
    if not isinstance(programs, list):
        raise SystemExit("Corpus JSON must contain a top-level 'programs' array.")

    by_type: dict[str, list[dict]] = {}

    for program in programs:
        if not isinstance(program, dict):
            continue
        curriculum = program.get("curriculum")
        if not isinstance(curriculum, dict):
            continue
        cores = curriculum.get("core_courses")
        if not isinstance(cores, list):
            continue
        for row in cores:
            if not isinstance(row, dict):
                continue
            raw_pt = row.get("primary_type")
            if isinstance(raw_pt, str) and raw_pt.strip():
                bucket = raw_pt.strip()
            else:
                bucket = "_missing_primary_type"
            by_type.setdefault(bucket, []).append(row)

    out_dir.mkdir(parents=True, exist_ok=True)

    indent = None if args.indent <= 0 else args.indent
    for primary_type, courses in sorted(by_type.items(), key=lambda x: x[0]):
        stem = safe_primary_type_filename(primary_type)
        out_path = out_dir / f"{stem}.json"
        payload = json.dumps(courses, indent=indent, ensure_ascii=False)
        if indent is not None:
            payload += "\n"
        out_path.write_text(payload, encoding="utf-8")
        print(f"{out_path} ({len(courses)} courses)", file=sys.stderr)


if __name__ == "__main__":
    main()
