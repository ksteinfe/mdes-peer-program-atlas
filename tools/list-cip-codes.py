"""List unique cip_code values across all programs in corpus/programs.json."""

import collections
import json
import pathlib

repo_root   = pathlib.Path(__file__).resolve().parent.parent
corpus_path = repo_root / "corpus" / "programs.json"

data     = json.loads(corpus_path.read_text(encoding="utf-8"))
programs = data.get("programs", [])

counts = collections.Counter(
    p.get("identity", {}).get("cip_code")
    for p in programs
    if isinstance(p, dict)
)

print(f"{'CIP code':<14}  {'Count':>5}")
print("─" * 24)
for code, n in sorted(counts.items(), key=lambda x: (x[0] is None, x[0] or "")):
    print(f"{str(code):<14}  {n:>5}")

print()
print(f"{len(counts)} unique value(s) across {len(programs)} programs")
