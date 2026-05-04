"""Normalize LLM-shaped program fragments before JSON Schema validation."""

from __future__ import annotations

from urllib.parse import urlparse

from typing import Any


def _title_from_url(url: str) -> str:
    path = [p for p in urlparse(url).path.strip("/").split("/") if p]
    tail = path[-1].replace("-", " ").replace("_", " ") if path else "home"
    return (tail[:1].upper() + tail[1:120]) if tail else "Web source"


def _apply_llm_rationale_layout(program: dict[str, Any]) -> None:
    """Ensure ``llm_rationales`` list exists; hoist ``derived_features`` on main sections."""
    if not isinstance(program, dict):
        return
    program.setdefault("llm_rationales", [])
    _hoist_derived_features(
        program, "positioning", ("positioning_summary", "positioning_tags")
    )
    _hoist_derived_features(
        program,
        "duration",
        ("length_in_berkeley_semesters", "duration_category"),
    )
    _hoist_derived_features(
        program,
        "degree_cost",
        (
            "base_currency",
            "exchange_rate_to_usd",
            "comparison_cost_usd",
            "cost_base_currency",
        ),
    )
    hoist_nested_curriculum_llm_rationales(program)


def _hoist_derived_features(
    program: dict[str, Any], sec: str, keys: tuple[str, ...]
) -> None:
    block = program.get(sec)
    if not isinstance(block, dict):
        return
    df = block.get("derived_features")
    if not isinstance(df, dict):
        return
    for k in keys:
        if k in df:
            block[k] = df[k]
    block.pop("derived_features", None)


def hoist_nested_curriculum_llm_rationales(program: dict[str, Any]) -> None:
    """
    Move nested ``curriculum.llm_rationales`` into top-level ``llm_rationales``.
    Discards stray nested keys ``sources``, ``derivation_notes`` (not in schema).
    """
    if not isinstance(program, dict):
        return
    cur = program.get("curriculum")
    if not isinstance(cur, dict):
        return
    base_u = str(program.get("base_url") or "").strip()
    root_lr = program.setdefault("llm_rationales", [])
    if not isinstance(root_lr, list):
        program["llm_rationales"] = []
        root_lr = program["llm_rationales"]

    cur.pop("sources", None)
    cur.pop("derivation_notes", None)

    nested_lr = cur.pop("llm_rationales", None)
    if isinstance(nested_lr, list):
        for item in nested_lr:
            if isinstance(item, dict):
                coerced = coerce_llm_rationale_object(
                    item, default_source_url=base_u
                )
                if coerced is not None:
                    root_lr.append(coerced)


def normalize_program_layout(program: dict[str, Any]) -> None:
    """
    Hoist nested ``llm_rationales`` into canonical top-level shape; strip unknown
    nested keys; normalize identity location and legacy degree_cost / curriculum keys.
    """
    _apply_llm_rationale_layout(program)
    if not isinstance(program, dict):
        return
    root_lr = program.get("llm_rationales")
    if not isinstance(root_lr, list):
        program["llm_rationales"] = []
        root_lr = program["llm_rationales"]

    ident = program.setdefault("identity", {})
    if not isinstance(ident, dict):
        program["identity"] = {}
        ident = program["identity"]
    ident.pop("sources", None)

    for sec in ("positioning", "duration", "degree_cost"):
        block = program.get(sec)
        if not isinstance(block, dict):
            continue
        block.pop("sources", None)
        block.pop("derivation_notes", None)
        nested = block.pop("llm_rationales", None)
        if isinstance(nested, list):
            base_u = str(program.get("base_url") or "").strip()
            for item in nested:
                if isinstance(item, dict):
                    coerced = coerce_llm_rationale_object(
                        item, default_source_url=base_u
                    )
                    if coerced is not None:
                        root_lr.append(coerced)

    if isinstance(ident, dict):
        loc = ident.get("location")
        if isinstance(loc, dict):
            ident.pop("location", None)
            c = str(loc.get("country") or "").strip()
            r = str(loc.get("state_or_region") or "").strip()
            parts = [p for p in (c, r) if p]
            if not str(ident.get("location_label") or "").strip():
                ident["location_label"] = ", ".join(parts) if parts else ""
        ident.pop("location", None)
        ident.setdefault("location_label", "")

    deg = program.get("degree_cost")
    if isinstance(deg, dict):
        leg = (
            "cost_base_currency_single",
            "cost_base_currency_domestic_or_resident",
            "cost_base_currency_international_or_nonresident",
        )
        if deg.get("cost_base_currency") is None:
            for k in leg:
                v = deg.get(k)
                if isinstance(v, (int, float)):
                    deg["cost_base_currency"] = float(v)
                    break
        for k in leg:
            deg.pop(k, None)
        for k in ("exchange_rate_date", "comparison_cost_method", "cost_basis"):
            deg.pop(k, None)

    cur = program.get("curriculum")
    if isinstance(cur, dict):
        cur.pop("derived_features", None)
        for k in (
            "has_required_core",
            "has_structured_electives",
            "has_open_electives",
            "has_required_studio_sequence",
            "has_required_thesis_or_capstone",
            "has_internship_or_professional_practice_requirement",
            "total_units_or_credits",
            "core_units_or_credits",
            "elective_units_or_credits",
            "typical_elective_units_or_credits",
            "average_required_course_or_slot_units",
        ):
            cur.pop(k, None)
        if "offers_specialization" not in cur:
            cur["offers_specialization"] = False
        else:
            os_ = cur.get("offers_specialization")
            if os_ is None:
                pass
            elif isinstance(os_, bool):
                pass
            else:
                cur["offers_specialization"] = False
        cur.pop("evidence_curriculum_summary", None)

    program.pop("derivation_notes", None)


def normalize_program_for_validation(program: dict[str, Any]) -> None:
    """Normalize layout before JSON Schema validation (mutates in place)."""
    normalize_program_layout(program)


def coerce_llm_rationale_object(
    item: dict[str, Any],
    *,
    default_source_url: str = "",
) -> dict[str, Any] | None:
    """
    Build corpus ``llmRationale`` dict from keys ``feature``, ``source_url``,
    ``note``, ``llm_title``, ``retrieved_date`` only (non-strings coerced to string).
    """
    if not isinstance(item, dict):
        return None
    feat = item.get("feature", "")
    if feat is not None and not isinstance(feat, str):
        feat = str(feat)
    note = item.get("note")
    if note is not None and not isinstance(note, str):
        note = str(note)
    note_s = "" if note is None else str(note).strip()
    su = item.get("source_url")
    if su is not None and not isinstance(su, str):
        su = str(su)
    su_s = str(su).strip() if su else ""
    if not su_s:
        su_s = (default_source_url or "").strip()
    lt = item.get("llm_title")
    lt_s = "" if lt is None else str(lt).strip()
    if su_s and not lt_s:
        lt_s = _title_from_url(su_s)[:200]
    rd = item.get("retrieved_date")
    rd_s = "" if rd is None else str(rd)
    return {
        "feature": "" if feat is None else str(feat),
        "source_url": su_s,
        "note": note_s,
        "llm_title": lt_s[:200] if lt_s else "",
        "retrieved_date": rd_s,
    }


def normalize_llm_rationales(program: dict[str, Any], *, default_source_url: str) -> int:
    """
    Coerce program-level ``llm_rationales`` entries that are bare strings into objects.
    Returns count of entries coerced or re-shaped.
    """
    fixed = 0
    base = (default_source_url or "").strip()
    arr = program.get("llm_rationales")
    if not isinstance(arr, list):
        program["llm_rationales"] = []
        return fixed
    new_list: list[Any] = []
    for item in arr:
        if isinstance(item, str):
            b = base.strip()
            new_list.append(
                {
                    "feature": "",
                    "source_url": b,
                    "note": item,
                    "llm_title": _title_from_url(b)[:200] if b else "",
                    "retrieved_date": "",
                }
            )
            fixed += 1
        elif isinstance(item, dict):
            coerced = coerce_llm_rationale_object(item, default_source_url=base)
            if coerced is not None:
                allowed = {
                    "feature",
                    "source_url",
                    "note",
                    "llm_title",
                    "retrieved_date",
                }
                if set(item.keys()) - allowed:
                    fixed += 1
                new_list.append(coerced)
        else:
            new_list.append(item)
    program["llm_rationales"] = new_list
    return fixed


def normalize_core_course_learning_outcomes(program: dict[str, Any]) -> None:
    """Ensure each curriculum.core_courses row has learning_outcomes: string[]."""
    cur = program.get("curriculum")
    if not isinstance(cur, dict):
        return
    rows = cur.get("core_courses")
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        lo = row.get("learning_outcomes")
        if lo is None or not isinstance(lo, list):
            row["learning_outcomes"] = []
            continue
        out: list[str] = []
        for x in lo:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                out.append(s)
        row["learning_outcomes"] = out


def _coerce_estimated_elective_count(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    if isinstance(v, float) and not isinstance(v, bool):
        if v != v:  # NaN
            return None
        return int(round(v))
    return None


def normalize_curriculum_electives(cur: dict[str, Any]) -> None:
    """
    Ensure curriculum uses ``electives`` (summary + estimated count only).

    Drops deprecated ``elective_requirements`` / ``elective_courses`` if present.
    """
    if not isinstance(cur, dict):
        return
    cur.pop("elective_requirements", None)
    cur.pop("elective_courses", None)
    el = cur.get("electives")
    if not isinstance(el, dict):
        el = {}
    summary = el.get("summary")
    if not isinstance(summary, str):
        summary = str(summary or "")
    cur["electives"] = {
        "summary": summary.strip(),
        "estimated_elective_course_count": _coerce_estimated_elective_count(
            el.get("estimated_elective_course_count")
        ),
    }
    cur.pop("derived_features", None)


def normalize_curriculum_electives_in_program(program: dict[str, Any]) -> None:
    hoist_nested_curriculum_llm_rationales(program)
    cur = program.get("curriculum")
    if isinstance(cur, dict):
        normalize_curriculum_electives(cur)


def coalesce_curriculum_subtree_from_llm(cur: dict[str, Any]) -> None:
    """
    Fix common LLM curriculum mistakes before JSON Schema validation.

    - Maps stray ``course_type`` → ``primary_type`` when needed and drops
      ``course_type`` (schema uses ``primary_type`` / ``secondary_type`` only).
    - If the model nested ``unit_system`` / ``sequencedness`` / ``curriculum_summary``
      inside ``derived_features``, lifts them to the curriculum root
      and drops ``derived_features``.
    - Normalizes ``electives``; strips any leftover ``derived_features``.
    - Ensures required nullable keys exist on ``core_courses`` rows.
    """
    if not isinstance(cur, dict):
        return
    cur.pop("evidence_curriculum_summary", None)
    df = cur.pop("derived_features", None)
    if isinstance(df, dict):
        for k in ("unit_system", "sequencedness", "curriculum_summary"):
            if k not in df:
                continue
            picked = df[k]
            prev = cur.get(k)
            if prev is None or (isinstance(prev, str) and not str(prev).strip()):
                cur[k] = picked
    normalize_curriculum_electives(cur)
    for row in cur.get("core_courses") or []:
        if not isinstance(row, dict):
            continue
        wrong = row.pop("course_type", None)
        pt = row.get("primary_type")
        if (pt is None or (isinstance(pt, str) and not pt.strip())) and isinstance(
            wrong, str
        ) and wrong.strip():
            row["primary_type"] = wrong.strip()
        row.setdefault("units_or_credits", None)
        row.setdefault("normalized_unit_weight", None)
        row.setdefault("secondary_type", None)
        row.setdefault("learning_outcomes", [])
        pt = row.get("primary_type")
        if not isinstance(pt, str) or not pt.strip():
            row["primary_type"] = "open_or_other"
        if row.get("primary_type") == "design_studio":
            row["secondary_type"] = None
    ospec = cur.get("offers_specialization")
    if ospec is True or ospec is False:
        cur["offers_specialization"] = ospec
    elif ospec is None:
        cur["offers_specialization"] = None
    else:
        cur["offers_specialization"] = False


def ensure_course_source_urls(program: dict[str, Any], base_url: str) -> None:
    """Set missing curriculum row source_url to program base_url (draft-friendly)."""
    u = (base_url or "").strip()
    if not u:
        return
    cur = program.get("curriculum")
    if not isinstance(cur, dict):
        return
    for key in ("core_courses",):
        rows = cur.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            su = row.get("source_url")
            if su is None or (isinstance(su, str) and not su.strip()):
                row["source_url"] = u
