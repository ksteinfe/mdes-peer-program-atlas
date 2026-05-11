"""
Set cip_code to null for any program that does not have an ipeds_unitid.

CIP codes are a US federal (IPEDS) classification. Only institutions with an
IPEDS UnitID on record are eligible. Run this after lookup-ipeds-unitids.py has
populated identity.ipeds_unitid for US programs.

Programs with ipeds_unitid set are left untouched; their cip_code will be (re-)
assigned when `reconsider-node identity` is run.
"""

import json
import pathlib
import sys


def migrate(corpus_path: pathlib.Path) -> None:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    programs = data.get("programs", [])
    nulled = 0
    skipped = 0
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        ident = prog.get("identity")
        if not isinstance(ident, dict):
            continue
        has_unitid = bool(ident.get("ipeds_unitid"))
        if has_unitid:
            skipped += 1
            continue
        if ident.get("cip_code") is not None:
            print(f"  NULL  {prog.get('program_id')}")
            ident["cip_code"] = None
            nulled += 1
    corpus_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nSet cip_code to null for {nulled} programs without ipeds_unitid.")
    if skipped:
        print(f"Left {skipped} programs with ipeds_unitid unchanged.")


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    target = repo_root / "corpus" / "programs.json"
    if not target.exists():
        print(f"Not found: {target}", file=sys.stderr)
        sys.exit(1)
    migrate(target)


if __name__ == "__main__":
    main()
