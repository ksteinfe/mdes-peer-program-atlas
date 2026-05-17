"""
Match each corpus program's host institution against the IPEDS HD table and
produce a merge-patch file that sets identity.ipeds_unitid.

Setup (one-time):
    Download https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip
    Unzip → rename the inner CSV to:
        peer-atlas-cli/references/ipeds_hd.csv

Usage (from repo root):
    python3 tools/lookup-ipeds-unitids.py
    python3 tools/lookup-ipeds-unitids.py --threshold-auto 0.90
    python3 tools/lookup-ipeds-unitids.py --all   # re-process programs that already have a unitid
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import pathlib
import re
import sys
from datetime import date

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT   = pathlib.Path(__file__).resolve().parent.parent
CORPUS_PATH = REPO_ROOT / "corpus" / "programs.json"
HD_PATH     = REPO_ROOT / "peer-atlas-cli" / "references" / "ipeds_hd.csv"
EXPORTS_DIR = REPO_ROOT / "exports"

THRESHOLD_AUTO   = 0.85   # score ≥ this → include in patch automatically
THRESHOLD_REVIEW = 0.60   # score ≥ this → flag for manual review

# Normalisation expansions applied to both sides before scoring
_EXPANSIONS = [
    (r"\buniv\b",    "university"),
    (r"\binst\b",    "institute"),
    (r"\bcoll\b",    "college"),
    (r"\btech\b",    "technology"),
    (r"\bthe\b",     ""),
    (r"&",           "and"),
    (r"['\-]",       " "),
    (r"\s+",         " "),
]

_EXCEL_RE = re.compile(r'^="(.*)"$')


def _strip_excel(s: str) -> str:
    m = _EXCEL_RE.match(s.strip())
    return m.group(1) if m else s.strip()


def _normalise(name: str) -> str:
    s = name.lower().strip()
    for pat, rep in _EXPANSIONS:
        s = re.sub(pat, rep, s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return s.strip()


def _city_from_location(location_label: str) -> str:
    """Extract city as the first comma-separated token."""
    return (location_label or "").split(",")[0].strip().lower()


def _domain_from_url(url: str) -> str:
    """Return registrable domain token for rough overlap check."""
    url = (url or "").lower().strip().rstrip("/")
    url = re.sub(r"^https?://", "", url)
    url = url.split("/")[0]  # hostname
    parts = url.split(".")
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return url


# ---------------------------------------------------------------------------
# Load IPEDS HD table
# ---------------------------------------------------------------------------

def load_hd(path: pathlib.Path) -> list[dict]:
    """
    Load HD CSV, stripping Excel `="..."` formula wrapping.
    Filters to ICLEVEL == 1 (4-year or above) to reduce noise.
    """
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            unitid   = _strip_excel(row.get("UNITID", ""))
            instnm   = _strip_excel(row.get("INSTNM", ""))
            city     = _strip_excel(row.get("CITY", "")).lower()
            stabbr   = _strip_excel(row.get("STABBR", "")).lower()
            webaddr  = _strip_excel(row.get("WEBADDR", "")).lower()
            iclevel  = _strip_excel(row.get("ICLEVEL", ""))
            if iclevel != "1":
                continue
            rows.append({
                "unitid":  unitid,
                "instnm":  instnm,
                "norm":    _normalise(instnm),
                "city":    city,
                "stabbr":  stabbr,
                "webaddr": webaddr,
                "domain":  _domain_from_url(webaddr),
            })
    return rows


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_match(
    prog_norm: str,
    prog_city: str,
    prog_domain: str,
    row: dict,
) -> float:
    name_sim = difflib.SequenceMatcher(None, prog_norm, row["norm"]).ratio()
    city_ok  = 1.0 if prog_city and prog_city == row["city"] else 0.0
    dom_ok   = 0.2 if prog_domain and row["domain"] and prog_domain == row["domain"] else 0.0

    score = name_sim * 0.7 + city_ok * 0.3 + dom_ok
    return min(score, 1.0)


def best_match(
    prog_norm: str,
    prog_city: str,
    prog_domain: str,
    hd_rows: list[dict],
) -> tuple[dict | None, float]:
    best_row   = None
    best_score = 0.0
    for row in hd_rows:
        s = score_match(prog_norm, prog_city, prog_domain, row)
        if s > best_score:
            best_score = s
            best_row   = row
    return best_row, best_score


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threshold-auto",   type=float, default=THRESHOLD_AUTO,
                        help=f"Min score for auto-patch (default {THRESHOLD_AUTO})")
    parser.add_argument("--threshold-review", type=float, default=THRESHOLD_REVIEW,
                        help=f"Min score to flag for review (default {THRESHOLD_REVIEW})")
    parser.add_argument("--all", action="store_true",
                        help="Re-process programs that already have an ipeds_unitid")
    args = parser.parse_args()

    if not HD_PATH.exists():
        sys.stderr.write(
            f"IPEDS HD file not found: {HD_PATH}\n"
            "Download HD2024.zip from https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip\n"
            "and unzip the inner CSV to that path.\n"
        )
        sys.exit(1)

    print(f"Loading IPEDS HD from {HD_PATH} …", flush=True)
    hd_rows = load_hd(HD_PATH)
    print(f"  {len(hd_rows)} 4-year institutions loaded.\n")

    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    programs = [p for p in corpus.get("programs", []) if isinstance(p, dict) and p.get("program_id")]

    patch_changes: list[dict] = []
    review_cases:  list[str]  = []
    no_match_cases: list[str] = []

    W = 40  # column width for display

    print(f"{'Program':<{W}}  {'Matched INSTNM':<{W}}  {'UnitID':>6}  Score  Confidence")
    print("─" * (W * 2 + 22))

    for prog in programs:
        pid   = prog["program_id"]
        ident = prog.get("identity") or {}

        if not args.all and ident.get("ipeds_unitid"):
            continue

        inst_name  = str(ident.get("institution_name") or "")
        location   = str(ident.get("location_label") or "")
        base_url   = str(prog.get("base_url") or "")

        prog_norm   = _normalise(inst_name)
        prog_city   = _city_from_location(location)
        prog_domain = _domain_from_url(base_url)

        row, score = best_match(prog_norm, prog_city, prog_domain, hd_rows)

        if row is None or score < args.threshold_review:
            label = "NO MATCH"
            no_match_cases.append(pid)
            unitid_s = "—"
            instnm_s = "—"
        elif score >= args.threshold_auto:
            label    = "AUTO"
            unitid_s = row["unitid"]
            instnm_s = row["instnm"]
            patch_changes.append({
                "program_id": pid,
                "path":       "identity.ipeds_unitid",
                "old_value":  ident.get("ipeds_unitid"),
                "new_value":  row["unitid"],
            })
        else:
            label    = "REVIEW"
            unitid_s = row["unitid"]
            instnm_s = row["instnm"]
            review_cases.append(f"  {pid:<{W}}  {instnm_s:<{W}}  {unitid_s:>6}  {score:.2f}")

        pid_s    = pid[:W]
        instnm_d = instnm_s[:W]
        print(f"{pid_s:<{W}}  {instnm_d:<{W}}  {unitid_s:>6}  {score:.2f}  {label}")

    # ── Summary ─────────────────────────────────────────────────────────────
    print()
    print(f"AUTO:     {len(patch_changes)} programs → will be written to patch file")
    print(f"REVIEW:   {len(review_cases)} programs → inspect and add manually via viewer")
    print(f"NO MATCH: {len(no_match_cases)} programs (likely international or not in IPEDS)")

    if not patch_changes:
        print("\nNo auto-matched programs — no patch file written.")
        return

    # ── Write patch ──────────────────────────────────────────────────────────
    EXPORTS_DIR.mkdir(exist_ok=True)
    today      = date.today().isoformat()
    patch_path = EXPORTS_DIR / f"ipeds-unitid-patch-{today}.json"
    patch = {
        "patch_metadata": {
            "created_at":          today,
            "created_by":          "tools/lookup-ipeds-unitids.py",
            "source_corpus_name":  "MDes Peer Program Comparator Corpus",
            "notes":               f"IPEDS UnitID auto-matched from HD2024; {len(patch_changes)} programs",
        },
        "changes": patch_changes,
    }
    patch_path.write_text(json.dumps(patch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nPatch written → {patch_path}")
    print(f"Apply with:  peer-atlas merge-patch {patch_path} --allow-new-paths")

    if review_cases:
        print("\nREVIEW cases (add manually via viewer or merge-patch):")
        for line in review_cases:
            print(line)


if __name__ == "__main__":
    main()
