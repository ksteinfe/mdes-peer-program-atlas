"""One-time migration: add identity.cip_code to all programs."""

import json
import pathlib
import sys


def migrate(corpus_path: pathlib.Path) -> None:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    programs = data.get("programs", [])
    added = 0
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        ident = prog.get("identity")
        if isinstance(ident, dict) and "cip_code" not in ident:
            ident["cip_code"] = "unknown"
            added += 1
    corpus_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{corpus_path.name}: added cip_code to {added} programs.")


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    target = repo_root / "corpus" / "programs.json"
    if not target.exists():
        print(f"Not found: {target}", file=sys.stderr)
        sys.exit(1)
    migrate(target)


if __name__ == "__main__":
    main()
