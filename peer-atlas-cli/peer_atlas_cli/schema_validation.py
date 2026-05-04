"""JSON Schema + category rule validation."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from jsonschema import Draft202012Validator

from peer_atlas_cli.categories import ids_for, load_categories
from peer_atlas_cli.program_sanitize import normalize_program_for_validation


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


def repair_invalid_category_enums(
    program: dict[str, Any],
    categories: dict[str, dict[str, Any]],
) -> list[str]:
    """
    Replace unknown category string values with the sentinel id ``INVALID`` (and
    apply a few structural fixes) so validation can proceed. Returns human-readable
    log lines including program_id and the rejected value.

    Call only when ``categories`` already includes an ``INVALID`` item for each
    vocabulary (see ``categories_and_rules/*.json``).
    """
    notes: list[str] = []
    pid = str(program.get("program_id") or "?")

    host_ids = ids_for("host_academic_models", categories)
    pos_ids = ids_for("positioning_tags", categories)
    dur_ids = ids_for("duration_categories", categories)
    unit_ids = ids_for("unit_systems", categories)
    seq_ids = ids_for("sequencedness", categories)
    ver_ids = ids_for("verification_statuses", categories)
    course_ids = ids_for("course_types", categories)

    ident = program.get("identity")
    if isinstance(ident, dict):
        hm = ident.get("host_academic_model")
        if hm is not None and str(hm).strip():
            v = str(hm).strip()
            if v not in host_ids:
                ident["host_academic_model"] = "INVALID"
                notes.append(
                    f"[{pid}] identity.host_academic_model: replaced invalid {v!r} with INVALID"
                )

    pos = program.get("positioning")
    if isinstance(pos, dict):
        tags = pos.get("positioning_tags")
        if isinstance(tags, list):
            new_tags: list[str] = []
            seen: set[str] = set()
            for i, t in enumerate(tags):
                if t is None or not str(t).strip():
                    notes.append(
                        f"[{pid}] positioning.positioning_tags[{i}]: dropped empty entry"
                    )
                    continue
                tid = str(t).strip()
                if tid not in pos_ids:
                    notes.append(
                        f"[{pid}] positioning.positioning_tags[{i}]: replaced invalid "
                        f"{tid!r} with INVALID"
                    )
                    tid = "INVALID"
                if tid in seen:
                    notes.append(
                        f"[{pid}] positioning.positioning_tags: dropped duplicate {tid!r}"
                    )
                    continue
                seen.add(tid)
                new_tags.append(tid)
            pos["positioning_tags"] = new_tags

    dur = program.get("duration")
    if isinstance(dur, dict):
        dc = dur.get("duration_category")
        if dc is not None and str(dc).strip():
            v = str(dc).strip()
            if v not in dur_ids:
                dur["duration_category"] = "INVALID"
                notes.append(
                    f"[{pid}] duration.duration_category: replaced invalid {v!r} with INVALID"
                )

    cur = program.get("curriculum")
    if isinstance(cur, dict):
        us = cur.get("unit_system")
        if us is not None and str(us).strip():
            v = str(us).strip()
            if v not in unit_ids:
                cur["unit_system"] = "INVALID"
                notes.append(
                    f"[{pid}] curriculum.unit_system: replaced invalid {v!r} with INVALID"
                )
        sq = cur.get("sequencedness")
        if sq is not None and str(sq).strip():
            v = str(sq).strip()
            if v not in seq_ids:
                cur["sequencedness"] = "INVALID"
                notes.append(
                    f"[{pid}] curriculum.sequencedness: replaced invalid {v!r} with INVALID"
                )

    ver = program.get("verification")
    if isinstance(ver, dict):
        vs = ver.get("status")
        if vs is not None and str(vs).strip():
            v = str(vs).strip()
            if v not in ver_ids:
                ver["status"] = "INVALID"
                notes.append(
                    f"[{pid}] verification.status: replaced invalid {v!r} with INVALID"
                )

    if isinstance(cur, dict):
        rows = cur.get("core_courses")
        if isinstance(rows, list):
            for i, c in enumerate(rows):
                if not isinstance(c, dict):
                    continue
                pt_raw = c.get("primary_type")
                pt = str(pt_raw).strip() if pt_raw is not None else ""
                if not pt:
                    c["primary_type"] = "INVALID"
                    notes.append(
                        f"[{pid}] curriculum.core_courses[{i}].primary_type: "
                        f"empty -> INVALID"
                    )
                    pt = "INVALID"
                elif pt not in course_ids:
                    c["primary_type"] = "INVALID"
                    notes.append(
                        f"[{pid}] curriculum.core_courses[{i}].primary_type: "
                        f"replaced invalid {pt_raw!r} with INVALID"
                    )
                    pt = "INVALID"

                st = c.get("secondary_type")
                if st is not None:
                    st_s = str(st).strip()
                    if not st_s:
                        c["secondary_type"] = None
                        notes.append(
                            f"[{pid}] curriculum.core_courses[{i}].secondary_type: "
                            f"cleared empty string"
                        )
                    elif st_s == "open_or_other":
                        c["secondary_type"] = "INVALID"
                        notes.append(
                            f"[{pid}] curriculum.core_courses[{i}].secondary_type: "
                            f"open_or_other not allowed as secondary -> INVALID"
                        )
                    elif st_s not in course_ids:
                        c["secondary_type"] = "INVALID"
                        notes.append(
                            f"[{pid}] curriculum.core_courses[{i}].secondary_type: "
                            f"replaced invalid {st!r} with INVALID"
                        )

                pt_now = str(c.get("primary_type") or "").strip()
                if pt_now == "design_studio" and c.get("secondary_type") is not None:
                    c["secondary_type"] = None
                    notes.append(
                        f"[{pid}] curriculum.core_courses[{i}]: "
                        f"cleared secondary_type for design_studio primary"
                    )

    return notes


def validate_program_shape(
    repo_root: pathlib.Path, program: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    normalize_program_for_validation(program)
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
    cbc = deg.get("cost_base_currency")
    if cbc is not None and not isinstance(cbc, (int, float)):
        p("degree_cost.cost_base_currency must be number or null")

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

    return errors


def validate_single_program(
    repo_root: pathlib.Path,
    program: dict[str, Any],
    *,
    category_repair_notes: list[str] | None = None,
    repair_invalid_enums: bool = True,
) -> list[str]:
    """Shape + category validation for one program (draft vs strict from ``atlas_ingest``)."""
    categories = load_categories(repo_root)
    if repair_invalid_enums:
        notes = repair_invalid_category_enums(program, categories)
        if category_repair_notes is not None:
            category_repair_notes.extend(notes)
    draft = program_uses_draft_validation(program)
    errors = validate_program_shape(repo_root, program)
    errors.extend(validate_program_categories(program, categories, draft=draft))
    return errors


def validate_corpus(
    repo_root: pathlib.Path,
    corpus: dict[str, Any],
    *,
    category_repair_notes: list[str] | None = None,
    repair_invalid_enums: bool = False,
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
        if repair_invalid_enums:
            ch = repair_invalid_category_enums(prog, categories)
            if category_repair_notes is not None:
                category_repair_notes.extend(ch)
        draft = program_uses_draft_validation(prog)
        errors.extend(validate_program_shape(repo_root, prog))
        errors.extend(validate_program_categories(prog, categories, draft=draft))

    return errors
