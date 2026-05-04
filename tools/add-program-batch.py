#!/usr/bin/env python3
"""
Run ``peer-atlas add-program`` once per row of a tab-separated file.

Expected columns (tab-separated):
  1. base_url   - full URL with https:// (same as add-program BASE_URL)
  2. program_id - stable slug (must not already exist in the corpus)
  3. query      - optional; passed as the third positional argument to add-program

Empty lines and lines whose first non-whitespace character is ``#`` are skipped.
Lines with fewer than two columns are skipped with a warning unless ``--strict``.

Usage (from repository root, with ``peer-atlas`` on PATH, e.g. venv activated)::

  python tools/add-program-batch.py path/to/queue.tsv
  python tools/add-program-batch.py --header programs.tsv -- --dry-run
  python tools/add-program-batch.py queue.tsv --peer-atlas peer-atlas -- --max-courses 0

The optional ``--`` separator forwards everything after it to each ``add-program`` invocation
(e.g. ``--dry-run``, ``--max-search-urls 15``).
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def _repo_root_from_script() -> Path:
    p = Path(__file__).resolve()
    # tools/add-program-batch.py -> repo root is parent of tools/
    return p.parent.parent


def _split_add_program_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """Return (batch_args, add_program_args) split at ``--`` if present."""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1 :]
    return argv, []


def parse_args(argv: list[str]) -> argparse.Namespace:
    batch_argv, passthrough = _split_add_program_args(argv)
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "tsv_path",
        type=Path,
        help="Tab-separated file: base_url, program_id, optional query",
    )
    p.add_argument(
        "--header",
        action="store_true",
        help="Skip the first non-empty, non-comment line (column names).",
    )
    p.add_argument(
        "--peer-atlas",
        default="peer-atlas",
        help="Executable name or path for the CLI (default: peer-atlas).",
    )
    p.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Working directory for each subprocess (default: repository root next to tools/).",
    )
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Run remaining rows after a failure; exit non-zero if any row failed.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if a non-comment line has fewer than two tab-separated columns.",
    )
    ns = p.parse_args(batch_argv)
    ns.add_program_args = passthrough
    return ns


def iter_rows(
    tsv_path: Path, *, header: bool
) -> tuple[list[tuple[int, str, str, str]], list[str], list[str]]:
    """
    Returns (rows, strict_issues, soft_warnings).

    strict_issues: lines with fewer than two tab-separated columns (for ``--strict``).
    soft_warnings: other skipped lines (e.g. empty URL/id after trim).
    """
    strict_issues: list[str] = []
    soft_warnings: list[str] = []
    rows: list[tuple[int, str, str, str]] = []
    text = tsv_path.read_text(encoding="utf-8")
    first_data = header
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if first_data:
            first_data = False
            continue
        parts = raw.rstrip("\n\r").split("\t")
        if len(parts) < 2:
            strict_issues.append(
                f"{tsv_path}:{line_no}: expected at least 2 tab-separated columns, got {len(parts)}"
            )
            continue
        base_url = parts[0].strip()
        program_id = parts[1].strip()
        query = parts[2].strip() if len(parts) > 2 else ""
        if not base_url or not program_id:
            soft_warnings.append(
                f"{tsv_path}:{line_no}: empty base_url or program_id after trim (skipped)"
            )
            continue
        rows.append((line_no, base_url, program_id, query))
    return rows, strict_issues, soft_warnings


def main() -> int:
    ns = parse_args(sys.argv[1:])
    tsv_path = ns.tsv_path.expanduser().resolve()
    if not tsv_path.is_file():
        print(f"error: not a file: {tsv_path}", file=sys.stderr)
        return 2

    cwd = ns.cwd.expanduser().resolve() if ns.cwd else _repo_root_from_script()
    if not cwd.is_dir():
        print(f"error: not a directory: {cwd}", file=sys.stderr)
        return 2

    rows, strict_issues, soft_warnings = iter_rows(tsv_path, header=ns.header)
    for w in soft_warnings:
        print(w, file=sys.stderr)
    for w in strict_issues:
        print(w, file=sys.stderr)
    if strict_issues and ns.strict:
        print("error: --strict set; fix short lines or remove them.", file=sys.stderr)
        return 2

    if not rows:
        print("error: no data rows to run (after skips / header).", file=sys.stderr)
        return 2

    exe = ns.peer_atlas
    failures: list[tuple[int, str, int]] = []

    for line_no, base_url, program_id, query in rows:
        cmd = [exe, "add-program", base_url, program_id]
        if query:
            cmd.append(query)
        cmd.extend(ns.add_program_args)
        print(f"\n--- line {line_no}: {program_id} ---", flush=True)
        print(shlex.join(cmd), flush=True)
        r = subprocess.run(cmd, cwd=cwd, env=os.environ.copy())
        if r.returncode != 0:
            failures.append((line_no, program_id, r.returncode))
            if not ns.continue_on_error:
                print(
                    f"error: add-program exited {r.returncode} at {tsv_path}:{line_no} ({program_id!r}).",
                    file=sys.stderr,
                )
                return r.returncode if r.returncode != 0 else 1

    if failures:
        print("\nCompleted with failures:", file=sys.stderr)
        for line_no, program_id, code in failures:
            print(f"  line {line_no}  {program_id!r}  exit {code}", file=sys.stderr)
        return 1

    print(f"\nDone: {len(rows)} program(s).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
