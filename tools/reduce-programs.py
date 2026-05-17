#!/usr/bin/env python3
import json
import sys
from pathlib import Path

corpus_path = Path(__file__).parent.parent / "corpus" / "programs.json"

with open(corpus_path) as f:
    data = json.load(f)

keep = {"program_id", "base_url", "identity", "date_added", "date_updated", "sources"}

reduced = [
    {k: v for k, v in program.items() if k in keep}
    for program in data["programs"]
]

json.dump({"programs": reduced}, sys.stdout, indent=2)
print()
