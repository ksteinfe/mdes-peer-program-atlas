#!/usr/bin/env python3
"""Split programs.json into groups of 12 with a reduced set of fields."""

import json
import pathlib

KEEP = {"program_id", "base_url", "identity", "date_added", "date_updated", "sources"}
CHUNK = 12

corpus = pathlib.Path(__file__).parent.parent / "corpus"
programs = json.loads((corpus / "programs.json").read_text())["programs"]

for start in range(0, len(programs), CHUNK):
    chunk = programs[start : start + CHUNK]
    end = start + len(chunk) - 1
    reduced = [{k: p[k] for k in KEEP if k in p} for p in chunk]
    filename = corpus / f"programs-simple-{start:02d}-{end:02d}.json"
    filename.write_text(json.dumps(reduced, indent=2))
    print(f"Wrote {filename.name} ({len(reduced)} programs)")
