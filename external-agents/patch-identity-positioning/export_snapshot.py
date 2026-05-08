#!/usr/bin/env python3
"""
Emit one snapshot file for external agent task patch-identity-positioning.

Writes under repo-root export-output/ (gitignored): a **.txt** filename whose
**body is JSON** (same structure as before). Identity, positioning, curriculum
summary snippets, electives summary, and filtered llm_rationales for every
program. Prints only the output filename to stdout (for logs / CI).

Usage (from repo root):
  python external-agents/patch-identity-positioning/export_snapshot.py
"""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

OUTPUT_DIR = "export-output"
FILENAME_PREFIX = "patch-identity-positioning_snapshot_"


def find_repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "corpus" / "programs.json").is_file():
            return p
    raise SystemExit(
        "Could not find corpus/programs.json. Run this script from the repo "
        "(or any path under it) so the corpus file can be located."
    )


def rationales_for_identity_positioning(program: dict) -> list:
    raw = program.get("llm_rationales")
    if not isinstance(raw, list):
        return []
    out: list = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        feat = item.get("feature")
        if not isinstance(feat, str):
            continue
        if feat.startswith("identity.") or feat.startswith("positioning."):
            out.append(item)
    return out


def curriculum_context_slice(program: dict) -> dict:
    """curriculum_summary + electives.summary only (read-only context for agents)."""
    cur = program.get("curriculum")
    if not isinstance(cur, dict):
        return {"curriculum_summary": "", "electives": {"summary": ""}}
    cs = cur.get("curriculum_summary")
    curriculum_summary = cs if isinstance(cs, str) else ""
    electives = cur.get("electives")
    summary = ""
    if isinstance(electives, dict):
        s = electives.get("summary")
        if isinstance(s, str):
            summary = s
    return {
        "curriculum_summary": curriculum_summary,
        "electives": {"summary": summary},
    }


def program_slice(program: dict) -> dict | None:
    pid = program.get("program_id")
    if not isinstance(pid, str) or not pid.strip():
        return None
    identity = program.get("identity")
    positioning = program.get("positioning")
    if not isinstance(identity, dict):
        identity = {}
    if not isinstance(positioning, dict):
        positioning = {}
    return {
        "program_id": pid.strip(),
        "identity": identity,
        "positioning": positioning,
        "curriculum": curriculum_context_slice(program),
        "llm_rationales": rationales_for_identity_positioning(program),
    }


def main() -> None:
    if len(sys.argv) > 1:
        raise SystemExit(
            "Usage: python export_snapshot.py\n"
            "Writes **all** programs (identity + positioning + curriculum summary "
            "snippets + filtered rationales) "
            f"to {OUTPUT_DIR}/ under the repo root; prints the filename only."
        )
    root = find_repo_root()
    path = root / "corpus" / "programs.json"
    with path.open(encoding="utf-8") as f:
        corpus = json.load(f)
    programs_raw = corpus.get("programs")
    if not isinstance(programs_raw, list):
        raise SystemExit("corpus.programs is missing or not an array")

    programs: list[dict] = []
    for p in programs_raw:
        if not isinstance(p, dict):
            continue
        row = program_slice(p)
        if row is not None:
            programs.append(row)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = root / OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{FILENAME_PREFIX}{ts}.txt"
    out_path = out_dir / filename

    snapshot = {
        "snapshot_metadata": {
            "task": "patch-identity-positioning",
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "corpus_file": "corpus/programs.json",
            "program_count": len(programs),
            "output_file": f"{OUTPUT_DIR}/{filename}",
        },
        "programs": programs,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(filename)


if __name__ == "__main__":
    main()
