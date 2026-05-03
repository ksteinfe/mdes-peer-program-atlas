"""JSON Schema + category rule validation."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from jsonschema import Draft202012Validator

from peer_atlas_cli.categories import ids_for, load_categories
from peer_atlas_cli.program_sanitize import migrate_record_canonical_shape


def program_uses_draft_validation(program: dict[str, Any]) -> bool:
    """Programs mid-ingest use program_draft.schema.json and relaxed category checks."""
    ai = program.get("atlas_ingest")
    if not isinstance(ai, dict):
        return False
    stage = str(ai.get("stage", "") or "").strip()
    return bool(stage) and stage != "complete"


def _schema_path(repo_root: pathlib.Path, name: str) -> pathlib.Path:
    return repo_root / "schemas" / name


def load_validator(repo_root: pathlib.Path, name: str) -> Draft202012Validator:
    path = _schema_path(repo_root, name)
    with path.open(encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema)


def validate_program_shape(
    repo_root: pathlib.Path, program: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    migrate_record_canonical_shape(program)
    name = (
        "program_draft.schema.json"
        if program_uses_draft_validation(program)
        else "program.schema.json"
    )
    v = load_validator(repo_root, name)
    for e in v.iter_errors(program):
        errors.append("/".join(str(p) for p in e.absolute_path) + ": " + e.message)
    return errors


def validate_patch_shape(repo_root: pathlib.Path, patch: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    v = load_validator(repo_root, "patch.schema.json")
    for e in v.iter_errors(patch):
        errors.append("/".join(str(p) for p in e.absolute_path) + ": " + e.message)
    return errors


def validate_program_categories(
    program: dict[str, Any],
    categories: dict[str, dict[str, Any]],
    prefix: str = "",
    *,
    draft: bool = False,
) -> list[str]:
    errors: list[str] = []
    pid = program.get("program_id", "?")

    def p(msg: str) -> None:
        errors.append(f"{prefix}[{pid}] {msg}")

    host_ids = ids_for("host_academic_models", categories)
    pos_ids = ids_for("positioning_tags", categories)
    dur_ids = ids_for("duration_categories", categories)
    unit_ids = ids_for("unit_systems", categories)
    seq_ids = ids_for("sequencedness", categories)
    ver_ids = ids_for("verification_statuses", categories)
    course_ids = ids_for("course_types", categories)

    ident = program.get("identity") or {}
    host_val = ident.get("host_academic_model")
    if host_val is not None and str(host_val).strip():
        if str(host_val) not in host_ids:
            p("identity.host_academic_model invalid")

    pos = program.get("positioning") or {}
    if not isinstance(pos, dict):
        pos = {}
    tags = pos.get("positioning_tags")
    if not isinstance(tags, list):
        if not draft:
            p("positioning.positioning_tags must be an array")
    else:
        seen_tag: set[str] = set()
        for i, t in enumerate(tags):
            if t is None or not str(t).strip():
                if not draft:
                    p(f"positioning.positioning_tags[{i}] must be non-empty")
                continue
            tid = str(t)
            if not draft:
                if tid in seen_tag:
                    p(f"positioning.positioning_tags duplicate {tid!r}")
                    continue
                seen_tag.add(tid)
            if tid not in pos_ids:
                p(f"positioning.positioning_tags[{i}] invalid")

    dur = program.get("duration") or {}
    if not isinstance(dur, dict):
        dur = {}
    dc = dur.get("duration_category")
    if dc is not None and str(dc).strip():
        if str(dc) not in dur_ids:
            p("duration.duration_category invalid")

    deg = program.get("degree_cost") or {}
    if not isinstance(deg, dict):
        deg = {}
    cc_usd = deg.get("comparison_cost_usd")
    if cc_usd is not None and not isinstance(cc_usd, (int, float)):
        p("degree_cost.comparison_cost_usd must be number or null")
    tdc = deg.get("total_degree_cost_base_currency")
    if tdc is not None and not isinstance(tdc, (int, float)):
        p(
            "degree_cost.total_degree_cost_base_currency must be number or null"
        )

    cur = program.get("curriculum") or {}
    if not isinstance(cur, dict):
        cur = {}
    us = cur.get("unit_system")
    if us is not None and str(us).strip():
        if str(us) not in unit_ids:
            p("curriculum.unit_system invalid")
    sq = cur.get("sequencedness")
    if sq is not None and str(sq).strip():
        if str(sq) not in seq_ids:
            p("curriculum.sequencedness invalid")

    ver = program.get("verification") or {}
    vs = ver.get("status")
    if vs is not None and str(vs).strip():
        if str(vs) not in ver_ids:
            p("verification.status invalid")

    for i, c in enumerate(cur.get("core_courses") or []):
        pt_raw = c.get("primary_type")
        if pt_raw is None or not str(pt_raw).strip():
            if not draft:
                p(f"curriculum.core_courses[{i}].primary_type invalid")
            continue
        pt = str(pt_raw)
        if pt not in course_ids:
            p(f"curriculum.core_courses[{i}].primary_type invalid")
        st = c.get("secondary_type")
        if st is not None:
            if str(st) not in course_ids:
                p(f"curriculum.core_courses[{i}].secondary_type invalid")
        if pt == "design_studio" and st is not None:
            p(f"curriculum.core_courses[{i}]: design_studio must have secondary_type null")
        nuw = c.get("normalized_unit_weight")
        if nuw is not None and not isinstance(nuw, (int, float)):
            p(f"curriculum.core_courses[{i}].normalized_unit_weight must be number or null")

    for i, e in enumerate(cur.get("elective_courses") or []):
        nuw = e.get("normalized_unit_weight") if isinstance(e, dict) else None
        if nuw is not None and not isinstance(nuw, (int, float)):
            p(
                f"curriculum.elective_courses[{i}].normalized_unit_weight must be number or null"
            )
        u = e.get("units_or_credits") if isinstance(e, dict) else None
        if u is not None and not isinstance(u, (int, float)):
            p(f"curriculum.elective_courses[{i}].units_or_credits must be number or null")

    return errors


def validate_single_program(repo_root: pathlib.Path, program: dict[str, Any]) -> list[str]:
    """Shape + category validation for one program (draft vs strict from ``atlas_ingest``)."""
    categories = load_categories(repo_root)
    draft = program_uses_draft_validation(program)
    errors = validate_program_shape(repo_root, program)
    errors.extend(validate_program_categories(program, categories, draft=draft))
    return errors


def validate_corpus(
    repo_root: pathlib.Path, corpus: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if not isinstance(corpus, dict):
        return ["corpus root must be an object"]
    programs = corpus.get("programs")
    if not isinstance(programs, list):
        errors.append("corpus.programs must be an array")
        return errors

    seen: set[str] = set()
    for prog in programs:
        if not isinstance(prog, dict):
            errors.append("each program must be an object")
            continue
        pid = prog.get("program_id")
        if not isinstance(pid, str) or not pid:
            errors.append("program missing program_id")
            continue
        if pid in seen:
            errors.append(f"duplicate program_id: {pid}")
        seen.add(pid)

    categories = load_categories(repo_root)
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        draft = program_uses_draft_validation(prog)
        errors.extend(validate_program_shape(repo_root, prog))
        errors.extend(validate_program_categories(prog, categories, draft=draft))

    return errors
