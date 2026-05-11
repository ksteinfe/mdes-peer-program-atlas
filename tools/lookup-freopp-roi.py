"""
Match each corpus program against the FREOPP Graduate ROI Dataset 2022 and
populate freopp_roi on each program.

Matching uses a two-step process:
  1. Filter FREOPP rows to those belonging to the program's institution (unit_id)
  2. Pass up to MAX_CANDIDATES rows to the LLM alongside program context
     (identity, duration, positioning) and ask it to select the best match

The LLM can match a row whose CIP code differs from the program's cip_code if
other signals (degree field, length, academic context) are a strong fit; in those
cases match_confidence is set to "low" on the stored freopp_roi object.

Reference file: peer-atlas-cli/references/freopp_roi2022.csv

Usage (from repo root, with venv active):
    python3 tools/lookup-freopp-roi.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

REPO_ROOT    = pathlib.Path(__file__).resolve().parent.parent
CSV_PATH     = REPO_ROOT / "peer-atlas-cli" / "references" / "freopp_roi2022.csv"
CORPUS_PATH  = REPO_ROOT / "corpus" / "programs.json"

MAX_CANDIDATES = 25   # max rows passed to LLM per program

# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

COLUMN_MAP: list[tuple[str, str, str]] = [
    ("Unit ID",                                              "unit_id",                                   "str"),
    ("Institution Name",                                     "institution_name",                          "str"),
    ("State FIPS Code",                                      "state_fips_code",                           "int"),
    ("State",                                                "state",                                     "str"),
    ("Credential Level",                                     "credential_level",                          "int"),
    ("Credential Level Description",                         "credential_level_description",              "str"),
    ("Program CIP Code",                                     "program_cip_code",                          "int"),
    ("Degree Field",                                         "degree_field",                              "str"),
    ("Degree Field Category",                                "degree_field_category",                     "str"),
    ("Control",                                              "control",                                   "str"),
    ("Carnegie Classification",                              "carnegie_classification",                   "str"),
    ("Research University?",                                 "research_university",                       "bool"),
    ("Ivy Leage University?",                                "ivy_league_university",                     "bool"),
    ("College Scorecard Cohort Count",                       "college_scorecard_cohort_count",            "int"),
    ("Estimated Age of Program Start",                       "estimated_age_of_program_start",            "float"),
    ("Estimated Age of Program Completion",                  "estimated_age_of_program_completion",       "float"),
    ("Program Length (Years)",                               "program_length_years",                      "float"),
    ("Annual Tuition",                                       "annual_tuition",                            "float"),
    ("All Years Tuition",                                    "all_years_tuition",                         "float"),
    ("Annual Education-related Spending",                    "annual_education_spending",                 "float"),
    ("All Years Education-related Spending",                 "all_years_education_spending",              "float"),
    ("Estimated Completion Rate",                            "estimated_completion_rate",                 "pct_str"),
    ("Absolute Increase in Lifetime Earnings",               "absolute_increase_lifetime_earnings",       "float"),
    ("Percentage Increase in Lifetime Earnings",             "percentage_increase_lifetime_earnings",     "pct_str"),
    ("Lifetime Return on Investment (ROI)",                  "lifetime_roi",                              "float"),
    ("Rank of Program by ROI (Master's)",                    "rank_by_roi_masters",                       "int"),
    ("Rank of Program by ROI (Advanced)",                    "rank_by_roi_advanced",                      "int"),
    ("ROI if Student Drops Out Before Finishing Degree",     "roi_dropout",                               "float"),
    ("ROI Weighted by Completion Likelihood",                "roi_weighted_completion",                   "float"),
    ("ROI Based on Education-Related Spending",              "roi_based_on_spending",                     "float"),
    ("ROI if Student Drops Out, Based on Spending",          "roi_dropout_based_on_spending",             "float"),
    ("ROI Weighted by Completion Likelihood, Based on Spending", "roi_weighted_completion_based_on_spending", "float"),
    ("Estimated Earnings at Graduation",                     "estimated_earnings_at_graduation",          "float"),
    ("Estimated Earnings at Age 30",                         "estimated_earnings_at_30",                  "float"),
    ("Estimated Earnings at Age 35",                         "estimated_earnings_at_35",                  "float"),
    ("Estimated Earnings at Age 40",                         "estimated_earnings_at_40",                  "float"),
    ("Estimated Earnings at Age 45",                         "estimated_earnings_at_45",                  "float"),
    ("Estimated Earnings at Age 50",                         "estimated_earnings_at_50",                  "float"),
    ("Estimated Earnings at Age 55",                         "estimated_earnings_at_55",                  "float"),
    ("Estimated Earnings at Age 60",                         "estimated_earnings_at_60",                  "float"),
    ("Estimated Counterfactual Earnings at Age 25",          "estimated_counterfactual_earnings_at_25",   "float"),
    ("Estimated Counterfactual Earnings at Age 30",          "estimated_counterfactual_earnings_at_30",   "float"),
    ("Estimated Counterfactual Earnings at Age 35",          "estimated_counterfactual_earnings_at_35",   "float"),
    ("Estimated Counterfactual Earnings at Age 40",          "estimated_counterfactual_earnings_at_40",   "float"),
    ("Estimated Counterfactual Earnings at Age 45",          "estimated_counterfactual_earnings_at_45",   "float"),
    ("Estimated Counterfactual Earnings at Age 50",          "estimated_counterfactual_earnings_at_50",   "float"),
    ("Estimated Counterfactual Earnings at Age 55",          "estimated_counterfactual_earnings_at_55",   "float"),
    ("Estimated Counterfactual Earnings at Age 60",          "estimated_counterfactual_earnings_at_60",   "float"),
]

# ---------------------------------------------------------------------------
# CIP code encoding (FREOPP convention)
# ---------------------------------------------------------------------------

def _cip_to_freopp_int(cip_code: str) -> int | None:
    """
    Encode a XX.XXXX CIP code to the integer format used by FREOPP:
      1. Take all digits left of the decimal, omitting any leading zero
      2. Take the first two digits right of the decimal
      3. Concatenate (no decimal)
    Examples: '50.0401' → 5004, '04.0201' → 402, '11.0101' → 1101
    """
    parts = (cip_code or "").split(".")
    if len(parts) != 2 or not parts[0] or len(parts[1]) < 2:
        return None
    try:
        left = int(parts[0])
        right_two = parts[1][:2]
        return int(f"{left}{right_two}")
    except ValueError:
        return None


def _cip_family(cip_code: str) -> int | None:
    """Return the 2-digit CIP family as an integer (e.g. '50.0401' → 50)."""
    parts = (cip_code or "").split(".")
    try:
        return int(parts[0])
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def _coerce(raw: str, kind: str):
    v = raw.strip()
    if v == "":
        return None
    if kind == "str":
        return v
    if kind == "pct_str":
        return v
    if kind == "bool":
        return v.strip() in ("1", "true", "True", "TRUE", "Yes", "yes", "YES")
    if kind == "int":
        try:
            return int(float(v))
        except ValueError:
            return None
    if kind == "float":
        try:
            return float(v)
        except ValueError:
            return None
    return v


def load_csv(path: pathlib.Path) -> dict[str, list[dict]]:
    """Build index: unit_id_str → [all rows for that institution]."""
    index: dict[str, list[dict]] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cred = row.get("Credential Level", "").strip()
            if cred not in ("5", "6", "7"):
                continue
            uid = row.get("Unit ID", "").strip()
            if not uid:
                continue
            obj: dict = {field: _coerce(row.get(csv_col, ""), kind)
                         for csv_col, field, kind in COLUMN_MAP}
            index.setdefault(uid, []).append(obj)
    return index


# ---------------------------------------------------------------------------
# Candidate prioritisation
# ---------------------------------------------------------------------------

def _tuition_compatible(program: dict, row: dict) -> bool:
    """Return False when annualized degree_cost does not match FREOPP annual_tuition.

    Annualizes degree_cost.comparison_cost_usd by dividing by program length in
    years (derived from duration.length_in_berkeley_semesters at 0.5 yr/semester),
    then compares against the FREOPP row's annual_tuition with a ±3 % tolerance.
    Accepts the row when any required value is missing.
    """
    corpus_total = (program.get("degree_cost") or {}).get("comparison_cost_usd")
    freopp_annual = row.get("annual_tuition")
    if corpus_total is None or freopp_annual is None or freopp_annual <= 0:
        return True

    berk_sem = (program.get("duration") or {}).get("length_in_berkeley_semesters")
    if not berk_sem or berk_sem <= 0:
        return True

    length_years = float(berk_sem) * 0.5
    corpus_annual = float(corpus_total) / length_years

    ratio = corpus_annual / float(freopp_annual)
    return 0.97 <= ratio <= 1.03


def prioritize_candidates(rows: list[dict], cip_code: str | None, program: dict) -> list[dict]:
    """Filter by tuition compatibility, sort by CIP proximity, cap at MAX_CANDIDATES.

    Tuition gate is applied first; if it would eliminate all rows, the gate is
    skipped so the LLM can still make a best-effort selection.
    """
    compatible = [r for r in rows if _tuition_compatible(program, r)]
    pool = compatible if compatible else rows   # fall back if gate rejects everything

    cip_int = _cip_to_freopp_int(cip_code) if cip_code else None
    family  = _cip_family(cip_code) if cip_code else None

    def priority(row: dict) -> int:
        rpc = row.get("program_cip_code")
        if cip_int is not None and rpc == cip_int:
            return 0                          # exact CIP match
        if family is not None and rpc is not None:
            row_family = rpc // 100           # 5004 // 100 = 50
            if row_family == family:
                return 1                      # same 2-digit CIP family
        return 2                              # unrelated CIP

    return sorted(pool, key=priority)[:MAX_CANDIDATES]


# ---------------------------------------------------------------------------
# LLM matching
# ---------------------------------------------------------------------------

def llm_select_match(
    client,
    program: dict,
    candidates: list[dict],
) -> tuple[dict | None, str | None, str | None]:
    """
    Ask the LLM to pick the best FREOPP row for the program.
    Returns (matched_row, confidence, reasoning).
    confidence is "high" or "low"; None when no match.
    """
    from peer_atlas_cli.llm_client import parse_json_response

    ident = program.get("identity") or {}
    dur   = program.get("duration") or {}
    pos   = program.get("positioning") or {}

    prog_ctx = {
        "program_name":               ident.get("program_name"),
        "credential_name":            ident.get("credential_name"),
        "degree_type":                ident.get("degree_type"),
        "host_academic_units":        ident.get("host_academic_units"),
        "host_academic_model":        ident.get("host_academic_model"),
        "cip_code":                   ident.get("cip_code"),
        "length_in_berkeley_semesters": dur.get("length_in_berkeley_semesters"),
        "positioning_summary":        pos.get("positioning_summary"),
    }

    rows_lines = []
    for i, row in enumerate(candidates):
        rows_lines.append(
            f"[{i}] CIP {row.get('program_cip_code')} | "
            f"{row.get('degree_field', '?')} | "
            f"Category: {row.get('degree_field_category', '?')} | "
            f"{row.get('program_length_years', '?')} yr | "
            f"{row.get('credential_level_description', '?')}"
        )

    user = (
        "Select the best FREOPP ROI record for this graduate program.\n\n"
        "PROGRAM:\n"
        + json.dumps(prog_ctx, indent=2)
        + "\n\nAVAILABLE FREOPP RECORDS (all from this institution):\n"
        + "\n".join(rows_lines)
        + """

Return a JSON object with exactly these keys:
{
  "matched_index": <integer index, or null if no row is a reasonable match>,
  "confidence": "high" or "low",
  "reasoning": "<one sentence>"
}

Rules:
- confidence "high": the CIP code in the matching row aligns well with the program
- confidence "low": the match is based on degree field / length / academic context but the CIP code does not align
- Return null for matched_index if no row is a reasonable fit
- Note: 1 Berkeley semester ≈ 0.5 academic years; a program length mismatch larger than 1 year is a strong signal against a match
"""
    )

    raw = client.complete(
        system="You select dataset rows. Return only valid JSON. No prose.",
        user=user,
        transcript_step="freopp-match",
    )
    parsed = parse_json_response(raw)
    if not isinstance(parsed, dict):
        return None, None, "LLM returned non-object"

    idx       = parsed.get("matched_index")
    conf      = parsed.get("confidence")
    reasoning = parsed.get("reasoning", "")

    if idx is None:
        return None, None, reasoning
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        return None, None, reasoning
    if not (0 <= idx < len(candidates)):
        return None, None, reasoning

    return candidates[idx], conf, reasoning


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("program_ids", nargs="*", metavar="PROGRAM_ID",
                        help="Specific program IDs to process (default: all programs in corpus)")
    args = parser.parse_args()
    filter_pids = set(args.program_ids) if args.program_ids else None

    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    # Load LLM config
    try:
        from peer_atlas_cli.config import load_env, require_llm_config
        from peer_atlas_cli.llm_client import get_client
        from peer_atlas_cli.repo_root import find_repo_root
        root = find_repo_root()
        load_env(root)
        provider, model, api_key, base_llm_url = require_llm_config()
        client = get_client(provider, api_key=api_key, model=model, base_url=base_llm_url)
        print(f"LLM: {model} · {provider}\n")
    except Exception as e:
        print(f"Failed to load LLM config: {e}", file=sys.stderr)
        print("Make sure the venv is active and .env is configured.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {CSV_PATH.name} …", flush=True)
    index = load_csv(CSV_PATH)
    print(f"  {len(index)} institutions indexed.\n")

    data     = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    programs = data.get("programs", [])

    matched_high = matched_low = skipped_no_uid = skipped_no_cip = no_rows = no_match = skipped_filter = 0

    for prog in programs:
        if not isinstance(prog, dict):
            continue
        pid   = prog.get("program_id", "?")
        if filter_pids is not None and pid not in filter_pids:
            skipped_filter += 1
            continue
        ident = prog.get("identity") or {}
        uid   = ident.get("ipeds_unitid")
        cip   = ident.get("cip_code")

        if not uid:
            prog["freopp_roi"] = None
            skipped_no_uid += 1
            continue

        if not cip or cip in ("unknown", "INVALID"):
            prog["freopp_roi"] = None
            skipped_no_cip += 1
            continue

        rows = index.get(str(uid), [])
        if not rows:
            prog["freopp_roi"] = None
            no_rows += 1
            continue

        candidates = prioritize_candidates(rows, cip, prog)
        print(f"  {pid}  ({len(rows)} rows → {len(candidates)} candidates)", flush=True)

        try:
            best, confidence, reasoning = llm_select_match(client, prog, candidates)
        except Exception as e:
            print(f"    LLM error: {e}", file=sys.stderr)
            prog["freopp_roi"] = None
            no_match += 1
            continue

        if best is None:
            print(f"    → no match  ({reasoning})")
            prog["freopp_roi"] = None
            no_match += 1
        else:
            conf_label = confidence or "unknown"
            print(f"    → matched [{conf_label}]  {best.get('degree_field', '?')}  ({reasoning})")
            row_with_conf = dict(best)
            row_with_conf["match_confidence"] = confidence
            prog["freopp_roi"] = row_with_conf
            if confidence == "high":
                matched_high += 1
            else:
                matched_low += 1

    CORPUS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    processed = len(programs) - skipped_filter
    print(f"\nResults ({processed} programs processed):")
    print(f"  {matched_high:>3} matched (high confidence — CIP aligned)")
    print(f"  {matched_low:>3} matched (low confidence — field/length fit, CIP did not align)")
    print(f"  {no_match:>3} not matched — LLM found no suitable row")
    print(f"  {no_rows:>3} not matched because FREOPP data does not have any record for this institution's unit_id")
    print(f"  {skipped_no_uid:>3} skipped — no ipeds_unitid")
    print(f"  {skipped_no_cip:>3} skipped — no/unknown cip_code")
    print(f"\nCorpus written → {CORPUS_PATH}")


if __name__ == "__main__":
    main()
