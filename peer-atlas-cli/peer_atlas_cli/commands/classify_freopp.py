"""classify-freopp — match freopp_roi for one program using the FREOPP ROI Dataset 2022."""

from __future__ import annotations

import csv
import json
import pathlib
import sys
from typing import Any

import click

from peer_atlas_cli.cli_progress import cli_bracket_line, cli_rule_line, cli_short_url
from peer_atlas_cli.config import load_env, require_llm_config
from peer_atlas_cli.corpus_io import load_corpus, program_by_id, write_corpus
from peer_atlas_cli.program_dates import bump_date_updated
from peer_atlas_cli.llm_client import get_client, parse_json_response
from peer_atlas_cli.llm_reporting import echo_validation_errors
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus

MAX_CANDIDATES = 25

# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

_COLUMN_MAP: list[tuple[str, str, str]] = [
    ("Unit ID",                                                  "unit_id",                                   "str"),
    ("Institution Name",                                         "institution_name",                          "str"),
    ("State FIPS Code",                                          "state_fips_code",                           "int"),
    ("State",                                                    "state",                                     "str"),
    ("Credential Level",                                         "credential_level",                          "int"),
    ("Credential Level Description",                             "credential_level_description",              "str"),
    ("Program CIP Code",                                         "program_cip_code",                          "int"),
    ("Degree Field",                                             "degree_field",                              "str"),
    ("Degree Field Category",                                    "degree_field_category",                     "str"),
    ("Control",                                                  "control",                                   "str"),
    ("Carnegie Classification",                                  "carnegie_classification",                   "str"),
    ("Research University?",                                     "research_university",                       "bool"),
    ("Ivy Leage University?",                                    "ivy_league_university",                     "bool"),
    ("College Scorecard Cohort Count",                           "college_scorecard_cohort_count",            "int"),
    ("Estimated Age of Program Start",                           "estimated_age_of_program_start",            "float"),
    ("Estimated Age of Program Completion",                      "estimated_age_of_program_completion",       "float"),
    ("Program Length (Years)",                                   "program_length_years",                      "float"),
    ("Annual Tuition",                                           "annual_tuition",                            "float"),
    ("All Years Tuition",                                        "all_years_tuition",                         "float"),
    ("Annual Education-related Spending",                        "annual_education_spending",                 "float"),
    ("All Years Education-related Spending",                     "all_years_education_spending",              "float"),
    ("Estimated Completion Rate",                                "estimated_completion_rate",                 "pct_str"),
    ("Absolute Increase in Lifetime Earnings",                   "absolute_increase_lifetime_earnings",       "float"),
    ("Percentage Increase in Lifetime Earnings",                 "percentage_increase_lifetime_earnings",     "pct_str"),
    ("Lifetime Return on Investment (ROI)",                      "lifetime_roi",                              "float"),
    ("Rank of Program by ROI (Master's)",                        "rank_by_roi_masters",                       "int"),
    ("Rank of Program by ROI (Advanced)",                        "rank_by_roi_advanced",                      "int"),
    ("ROI if Student Drops Out Before Finishing Degree",         "roi_dropout",                               "float"),
    ("ROI Weighted by Completion Likelihood",                    "roi_weighted_completion",                   "float"),
    ("ROI Based on Education-Related Spending",                  "roi_based_on_spending",                     "float"),
    ("ROI if Student Drops Out, Based on Spending",              "roi_dropout_based_on_spending",             "float"),
    ("ROI Weighted by Completion Likelihood, Based on Spending", "roi_weighted_completion_based_on_spending", "float"),
    ("Estimated Earnings at Graduation",                         "estimated_earnings_at_graduation",          "float"),
    ("Estimated Earnings at Age 30",                             "estimated_earnings_at_30",                  "float"),
    ("Estimated Earnings at Age 35",                             "estimated_earnings_at_35",                  "float"),
    ("Estimated Earnings at Age 40",                             "estimated_earnings_at_40",                  "float"),
    ("Estimated Earnings at Age 45",                             "estimated_earnings_at_45",                  "float"),
    ("Estimated Earnings at Age 50",                             "estimated_earnings_at_50",                  "float"),
    ("Estimated Earnings at Age 55",                             "estimated_earnings_at_55",                  "float"),
    ("Estimated Earnings at Age 60",                             "estimated_earnings_at_60",                  "float"),
    ("Estimated Counterfactual Earnings at Age 25",              "estimated_counterfactual_earnings_at_25",   "float"),
    ("Estimated Counterfactual Earnings at Age 30",              "estimated_counterfactual_earnings_at_30",   "float"),
    ("Estimated Counterfactual Earnings at Age 35",              "estimated_counterfactual_earnings_at_35",   "float"),
    ("Estimated Counterfactual Earnings at Age 40",              "estimated_counterfactual_earnings_at_40",   "float"),
    ("Estimated Counterfactual Earnings at Age 45",              "estimated_counterfactual_earnings_at_45",   "float"),
    ("Estimated Counterfactual Earnings at Age 50",              "estimated_counterfactual_earnings_at_50",   "float"),
    ("Estimated Counterfactual Earnings at Age 55",              "estimated_counterfactual_earnings_at_55",   "float"),
    ("Estimated Counterfactual Earnings at Age 60",              "estimated_counterfactual_earnings_at_60",   "float"),
]


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _coerce(raw: str, kind: str) -> Any:
    v = raw.strip()
    if v == "":
        return None
    if kind == "str":
        return v
    if kind == "pct_str":
        return v
    if kind == "bool":
        return v in ("1", "true", "True", "TRUE", "Yes", "yes", "YES")
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


def load_freopp_csv(csv_path: pathlib.Path) -> dict[str, list[dict]]:
    """Build index: unit_id → [all rows for that institution] (levels 5, 6, 7)."""
    index: dict[str, list[dict]] = {}
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("Credential Level", "").strip() not in ("5", "6", "7"):
                continue
            uid = row.get("Unit ID", "").strip()
            if not uid:
                continue
            obj = {field: _coerce(row.get(col, ""), kind) for col, field, kind in _COLUMN_MAP}
            index.setdefault(uid, []).append(obj)
    return index


# ---------------------------------------------------------------------------
# CIP encoding
# ---------------------------------------------------------------------------

def _cip_to_freopp_int(cip_code: str) -> int | None:
    """'50.0401' → 5004, '04.0201' → 402."""
    parts = (cip_code or "").split(".")
    if len(parts) != 2 or not parts[0] or len(parts[1]) < 2:
        return None
    try:
        return int(f"{int(parts[0])}{parts[1][:2]}")
    except ValueError:
        return None


def _cip_family(cip_code: str) -> int | None:
    try:
        return int((cip_code or "").split(".")[0])
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Tuition gate
# ---------------------------------------------------------------------------

def _tuition_compatible(program: dict, row: dict) -> bool:
    """Annualize degree_cost.comparison_cost_usd and compare to FREOPP annual_tuition (±3%)."""
    corpus_total  = (program.get("degree_cost") or {}).get("comparison_cost_usd")
    freopp_annual = row.get("annual_tuition")
    if corpus_total is None or freopp_annual is None or freopp_annual <= 0:
        return True
    berk_sem = (program.get("duration") or {}).get("length_in_berkeley_semesters")
    if not berk_sem or berk_sem <= 0:
        return True
    corpus_annual = float(corpus_total) / (float(berk_sem) * 0.5)
    ratio = corpus_annual / float(freopp_annual)
    return 0.97 <= ratio <= 1.03


# ---------------------------------------------------------------------------
# Candidate prioritisation
# ---------------------------------------------------------------------------

def prioritize_candidates(rows: list[dict], cip_code: str | None, program: dict) -> list[dict]:
    """Apply tuition gate, sort by CIP proximity, cap at MAX_CANDIDATES."""
    compatible = [r for r in rows if _tuition_compatible(program, r)]
    pool = compatible if compatible else rows

    cip_int = _cip_to_freopp_int(cip_code) if cip_code else None
    family  = _cip_family(cip_code) if cip_code else None

    def _priority(row: dict) -> int:
        rpc = row.get("program_cip_code")
        if cip_int is not None and rpc == cip_int:
            return 0
        if family is not None and rpc is not None and rpc // 100 == family:
            return 1
        return 2

    return sorted(pool, key=_priority)[:MAX_CANDIDATES]


# ---------------------------------------------------------------------------
# LLM matching
# ---------------------------------------------------------------------------

def run_freopp_match_step(
    *,
    client: Any,
    program: dict,
    candidates: list[dict],
) -> tuple[dict | None, str | None, str | None]:
    """
    Ask the LLM to select the best FREOPP row from candidates.
    Returns (matched_row, confidence, reasoning).
    confidence is 'high' (CIP aligned) or 'low' (non-CIP signals), None when no match.
    """
    ident = program.get("identity") or {}
    dur   = program.get("duration") or {}
    pos   = program.get("positioning") or {}

    prog_ctx = {
        "program_name":                 ident.get("program_name"),
        "credential_name":              ident.get("credential_name"),
        "degree_type":                  ident.get("degree_type"),
        "host_academic_units":          ident.get("host_academic_units"),
        "host_academic_model":          ident.get("host_academic_model"),
        "cip_code":                     ident.get("cip_code"),
        "length_in_berkeley_semesters": dur.get("length_in_berkeley_semesters"),
        "positioning_summary":          pos.get("positioning_summary"),
    }

    rows_lines = [
        f"[{i}] CIP {r.get('program_cip_code')} | {r.get('degree_field','?')} | "
        f"Category: {r.get('degree_field_category','?')} | "
        f"{r.get('program_length_years','?')} yr | {r.get('credential_level_description','?')}"
        for i, r in enumerate(candidates)
    ]

    user = (
        "Select the best FREOPP ROI record for this graduate program.\n\n"
        "PROGRAM:\n" + json.dumps(prog_ctx, indent=2) +
        "\n\nAVAILABLE FREOPP RECORDS (all from this institution):\n" +
        "\n".join(rows_lines) +
        """

Return a JSON object with exactly these keys:
{
  "matched_index": <integer index, or null if no row is a reasonable match>,
  "confidence": "high" or "low",
  "reasoning": "<one sentence>"
}

Rules:
- confidence "high": the CIP code in the matching row aligns well with the program
- confidence "low": matched on degree field/length/academic context but CIP does not align
- Return null for matched_index if no row is a reasonable fit
- Note: 1 Berkeley semester ≈ 0.5 academic years
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
    reasoning = str(parsed.get("reasoning", ""))

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
# Click command
# ---------------------------------------------------------------------------

@click.command("classify-freopp")
@click.argument("program_id")
@click.option("--dry-run", is_flag=True, help="Run matching but do not write corpus.")
def classify_freopp_cmd(program_id: str, dry_run: bool) -> None:
    """Match freopp_roi for PROGRAM_ID against the FREOPP Graduate ROI Dataset 2022.

    Filters candidates by institution (ipeds_unitid), applies a tuition
    compatibility gate, then uses the LLM to select the best row. Sets
    freopp_roi to null when the program lacks ipeds_unitid or cip_code, when
    no rows exist for the institution, or when the LLM finds no suitable match.
    """
    root = find_repo_root()
    load_env(root)
    provider, model, api_key, base_llm_url = require_llm_config()

    pid = (program_id or "").strip()
    if not pid:
        raise click.UsageError("program_id must be non-empty.")

    csv_path = root / "peer-atlas-cli" / "references" / "freopp_roi2022.csv"
    if not csv_path.exists():
        raise click.ClickException(
            f"FREOPP CSV not found: {csv_path}\n"
            "Download HD2024.zip from https://nces.ed.gov/ipeds and place the CSV at that path."
        )

    corpus  = load_corpus(root)
    program = program_by_id(corpus, pid)
    if program is None:
        raise click.ClickException(f"Unknown program_id: {pid!r}")

    ident = program.get("identity") or {}
    uid   = ident.get("ipeds_unitid")
    cip   = ident.get("cip_code")

    host = base_llm_url or "https://api.openai.com"
    cli_rule_line("=")
    cli_bracket_line("freopp", "setup", f"{pid} · {model} · {provider} · {cli_short_url(host)}")
    cli_rule_line("-")

    if not uid:
        program["freopp_roi"] = None
        cli_bracket_line("freopp", "skip", "no ipeds_unitid — freopp_roi set to null")
        _finish(corpus, program, root, dry_run, pid)
        return

    if not cip or cip in ("unknown", "INVALID"):
        program["freopp_roi"] = None
        cli_bracket_line("freopp", "skip", "no valid cip_code — freopp_roi set to null")
        _finish(corpus, program, root, dry_run, pid)
        return

    cli_bracket_line("freopp", "csv", f"loading {csv_path.name} …")
    index = load_freopp_csv(csv_path)

    rows = index.get(str(uid), [])
    if not rows:
        program["freopp_roi"] = None
        cli_bracket_line("freopp", "skip", f"no FREOPP rows for unit_id {uid}")
        _finish(corpus, program, root, dry_run, pid)
        return

    candidates = prioritize_candidates(rows, cip, program)
    cli_bracket_line("freopp", "match",
                     f"{len(rows)} institution rows → {len(candidates)} candidates → LLM")

    client = get_client(provider, api_key=api_key, model=model, base_url=base_llm_url)

    try:
        best, confidence, reasoning = run_freopp_match_step(
            client=client,
            program=program,
            candidates=candidates,
        )
    except Exception as e:
        raise click.ClickException(f"LLM error during FREOPP matching: {e}") from e

    if best is None:
        program["freopp_roi"] = None
        cli_bracket_line("freopp", "result", f"no match — {reasoning}")
    else:
        row_with_conf = {**best, "match_confidence": confidence}
        program["freopp_roi"] = row_with_conf
        cli_bracket_line("freopp", "result",
                         f"[{confidence}] {best.get('degree_field','?')} — {reasoning}")

    _finish(corpus, program, root, dry_run, pid)


def _finish(
    corpus: dict,
    program: dict,
    root: pathlib.Path,
    dry_run: bool,
    pid: str,
) -> None:
    bump_date_updated(program)
    enum_notes: list[str] = []
    errs = validate_corpus(root, corpus, category_repair_notes=enum_notes, repair_invalid_enums=True)
    for line in enum_notes:
        cli_bracket_line("freopp", "enum-repair", line, indent_tabs=1)
    if errs:
        echo_validation_errors(errs, intro="Corpus invalid after classify-freopp.")
        sys.exit(1)
    if dry_run:
        cli_bracket_line("freopp", "done", "dry-run OK")
        return
    write_corpus(root, corpus)
    cli_rule_line("=")
    cli_bracket_line("freopp", "done", f"wrote freopp_roi · {pid}")
