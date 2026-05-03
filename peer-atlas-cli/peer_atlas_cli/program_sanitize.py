"""Normalize LLM-shaped program fragments before JSON Schema validation."""

from __future__ import annotations

from urllib.parse import urlparse

from typing import Any

_LEGACY_FEATURE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("duration.derived_features.", "duration."),
    ("degree_cost.derived_features.", "degree_cost."),
)
def _upgrade_feature_path(s: str) -> str:
    out = str(s or "")
    for old, new in _LEGACY_FEATURE_PREFIXES:
        out = out.replace(old, new)
    return out


def _title_from_url(url: str) -> str:
    path = [p for p in urlparse(url).path.strip("/").split("/") if p]
    tail = path[-1].replace("-", " ").replace("_", " ") if path else "home"
    return (tail[:1].upper() + tail[1:120]) if tail else "Web source"


def _rationale_source_urls_seen(root_lr: list[Any]) -> set[str]:
    out: set[str] = set()
    for r in root_lr:
        if not isinstance(r, dict):
            continue
        u = str(r.get("source_url") or "").strip()
        if u:
            out.add(u)
    return out


def bibliography_dict_to_rationale(
    raw: dict[str, Any],
    *,
    feature: str = "",
) -> dict[str, Any]:
    """
    Map a legacy bibliography object (``url``, ``llm_title``, ``llm_summary``,
    ``retrieved_date``) onto one ``llmRationale`` row (``note`` holds summary text).
    """
    d = dict(raw)
    d.pop("direct_text", None)
    d.pop("notes", None)
    d.pop("source_id", None)
    url = str(d.get("url") or d.get("source_url") or "").strip()
    title = str(d.get("llm_title") or "").strip()
    if url and not title:
        title = _title_from_url(url)[:200]
    summ = d.get("llm_summary")
    summ_s = "" if summ is None else str(summ)
    rd = d.get("retrieved_date")
    rd_s = "" if rd is None else str(rd)
    return {
        "feature": str(feature or ""),
        "source_url": url,
        "note": summ_s,
        "llm_title": title[:200] if title else "",
        "retrieved_date": rd_s,
    }


def migrate_record_canonical_shape(program: dict[str, Any]) -> None:
    """
    In-place migration: ``derivation_notes`` → ``llm_rationales`` (``feature`` key),
    ``identity.sources`` → ``llm_rationales`` bibliography rows, flatten ``derived_features`` on
    positioning / duration / degree_cost,
    and hoist nested ``curriculum.sources`` / ``curriculum.derivation_notes`` to the
    program top level.
    Safe to call multiple times.
    """
    if not isinstance(program, dict):
        return

    if "derivation_notes" in program:
        legacy = program.pop("derivation_notes")
        cur = program.get("llm_rationales")
        if not isinstance(cur, list):
            cur = []
        if isinstance(legacy, list):
            cur.extend(legacy)
        program["llm_rationales"] = cur

    program.setdefault("llm_rationales", [])
    lr = program["llm_rationales"]
    if isinstance(lr, list):
        for item in lr:
            if not isinstance(item, dict):
                continue
            if "feature" not in item and "derived_feature" in item:
                item["feature"] = _upgrade_feature_path(
                    str(item.pop("derived_feature", ""))
                )
            elif "feature" in item:
                item["feature"] = _upgrade_feature_path(str(item.get("feature", "")))

    ident = program.get("identity")
    if isinstance(ident, dict) and "sources" in ident:
        legacy_src = ident.pop("sources")
        root_lr = program.setdefault("llm_rationales", [])
        if not isinstance(root_lr, list):
            program["llm_rationales"] = []
            root_lr = program["llm_rationales"]
        if isinstance(legacy_src, list):
            seen = _rationale_source_urls_seen(root_lr)
            for s in legacy_src:
                if not isinstance(s, dict):
                    continue
                r = bibliography_dict_to_rationale(s, feature="identity.citation")
                u = r["source_url"]
                if u and u in seen:
                    continue
                if u:
                    seen.add(u)
                root_lr.append(r)

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
            "total_degree_cost_base_currency",
        ),
    )

    hoist_curriculum_sources_and_derivation_notes_to_program(program)


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


def hoist_curriculum_sources_and_derivation_notes_to_program(
    program: dict[str, Any],
) -> None:
    """
    Move ``curriculum.sources`` into top-level ``llm_rationales`` (dedupe by
    ``source_url``) and ``curriculum.derivation_notes`` / legacy
    ``curriculum.llm_rationales`` into top-level ``llm_rationales``. Removes those
    keys from ``curriculum``.
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

    nested_lr = cur.pop("llm_rationales", None)
    if isinstance(nested_lr, list):
        for item in nested_lr:
            if isinstance(item, dict):
                coerced = coerce_llm_rationale_object(
                    item, default_source_url=base_u
                )
                if coerced is not None:
                    root_lr.append(coerced)

    notes = cur.pop("derivation_notes", None)
    if isinstance(notes, list):
        for item in notes:
            if isinstance(item, dict):
                coerced = coerce_llm_rationale_object(
                    item, default_source_url=base_u
                )
                if coerced is not None:
                    root_lr.append(coerced)

    srcs = cur.pop("sources", None)
    if isinstance(srcs, list) and srcs:
        seen = _rationale_source_urls_seen(root_lr)
        for s in srcs:
            if not isinstance(s, dict):
                continue
            r = bibliography_dict_to_rationale(s, feature="curriculum.citation")
            u = r["source_url"]
            if u and u in seen:
                continue
            if u:
                seen.add(u)
            root_lr.append(r)


def normalize_program_layout(program: dict[str, Any]) -> None:
    """
    Hoist nested ``llm_rationales`` / ``sources`` into canonical top-level shape, and
    migrate legacy fields (nested location, old degree_cost keys, curriculum flags).
    """
    migrate_record_canonical_shape(program)
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

    for sec in ("positioning", "duration", "degree_cost"):
        block = program.get(sec)
        if not isinstance(block, dict):
            continue
        for nk in ("llm_rationales", "derivation_notes"):
            nested = block.pop(nk, None)
            if isinstance(nested, list):
                root_lr.extend(nested)
        srcs = block.pop("sources", None)
        if isinstance(srcs, list) and srcs:
            seen = _rationale_source_urls_seen(root_lr)
            for s in srcs:
                if not isinstance(s, dict):
                    continue
                r = bibliography_dict_to_rationale(s, feature=f"{sec}.citation")
                u = r["source_url"]
                if u and u in seen:
                    continue
                if u:
                    seen.add(u)
                root_lr.append(r)

    # Hoist nested curriculum bibliography / notes to program top level (canonical shape).
    cur_block = program.get("curriculum")
    if isinstance(cur_block, dict):
        hoist_curriculum_sources_and_derivation_notes_to_program(program)

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
            "total_degree_cost_base_currency_single",
            "total_degree_cost_base_currency_domestic_or_resident",
            "total_degree_cost_base_currency_international_or_nonresident",
        )
        if deg.get("total_degree_cost_base_currency") is None:
            for k in leg:
                v = deg.get(k)
                if isinstance(v, (int, float)):
                    deg["total_degree_cost_base_currency"] = float(v)
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


def finalize_top_level_sources_into_rationales(program: dict[str, Any]) -> int:
    """
    Convert legacy top-level ``sources[]`` into ``llm_rationales`` rows, then remove
    ``sources``. Returns how many rows were appended.
    """
    migrate_record_canonical_shape(program)
    srcs = program.pop("sources", None)
    if not isinstance(srcs, list) or not srcs:
        return 0
    root_lr = program.setdefault("llm_rationales", [])
    if not isinstance(root_lr, list):
        program["llm_rationales"] = []
        root_lr = program["llm_rationales"]
    seen = _rationale_source_urls_seen(root_lr)
    added = 0
    for s in srcs:
        if not isinstance(s, dict):
            continue
        r = bibliography_dict_to_rationale(s, feature="program.citation")
        u = r["source_url"]
        if u and u in seen:
            continue
        if u:
            seen.add(u)
        root_lr.append(r)
        added += 1
    return added


def append_bibliography_dicts_as_rationales(
    program: dict[str, Any],
    items: list[Any],
    *,
    feature: str = "ingest.citation",
) -> None:
    """Append legacy-shaped bibliography dicts as ``llm_rationales`` rows (dedupe by URL)."""
    if not items:
        return
    root_lr = program.setdefault("llm_rationales", [])
    if not isinstance(root_lr, list):
        program["llm_rationales"] = []
        root_lr = program["llm_rationales"]
    seen = _rationale_source_urls_seen(root_lr)
    for item in items:
        if not isinstance(item, dict):
            continue
        r = bibliography_dict_to_rationale(item, feature=feature)
        u = r["source_url"]
        if u and u in seen:
            continue
        if u:
            seen.add(u)
        root_lr.append(r)


def coerce_llm_rationale_object(
    item: dict[str, Any],
    *,
    default_source_url: str = "",
) -> dict[str, Any] | None:
    """
    Map LLM / legacy keys onto the corpus ``llmRationale`` shape: ``feature``,
    ``source_url``, ``note``, ``llm_title``, ``retrieved_date`` (no ``rationale``,
    ``reason``, etc.).
    """
    if not isinstance(item, dict):
        return None
    d = dict(item)
    base = (default_source_url or "").strip()
    if "source_id" in d and not str(d.get("source_url") or "").strip():
        sid = d.pop("source_id", "")
        d["source_url"] = str(sid) if sid else base
    if "derived_feature" in d and not str(d.get("feature") or "").strip():
        d["feature"] = _upgrade_feature_path(str(d.pop("derived_feature", "")))
    feat = d.get("feature", "")
    if feat is not None and not isinstance(feat, str):
        feat = str(feat)
    note = d.get("note")
    if note is None:
        for k in ("rationale", "reason", "explanation", "comment"):
            v = d.get(k)
            if v is not None:
                note = v
                break
    if note is not None and not isinstance(note, str):
        note = str(note)
    note_s = "" if note is None else str(note).strip()
    if not note_s:
        ls = d.get("llm_summary")
        if ls is not None:
            note_s = str(ls).strip()
    su = d.get("source_url")
    if su is None or (isinstance(su, str) and not su.strip()):
        su = d.get("url") or base
    if su is not None and not isinstance(su, str):
        su = str(su)
    su_s = str(su).strip() if su else ""
    lt = d.get("llm_title")
    lt_s = "" if lt is None else str(lt).strip()
    if su_s and not lt_s:
        lt_s = _title_from_url(su_s)[:200]
    rd = d.get("retrieved_date")
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
    Migrates legacy ``source_id`` / ``derived_feature`` keys. Returns count fixed.
    """
    migrate_record_canonical_shape(program)
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


# Backwards-compatible name for callers/tests
normalize_derivation_notes = normalize_llm_rationales


def strip_legacy_source_id_fields(program: dict[str, Any]) -> None:
    """Remove deprecated source_id from legacy top-level ``sources`` (before finalize)."""
    migrate_record_canonical_shape(program)
    srcs = program.get("sources")
    if not isinstance(srcs, list):
        return
    for s in srcs:
        if isinstance(s, dict) and "source_id" in s:
            s.pop("source_id", None)


def migrate_course_source_id_to_url(program: dict[str, Any]) -> None:
    """Map legacy curriculum source_id to source_url using top-level ``sources`` when present."""
    migrate_record_canonical_shape(program)
    id_to_url: dict[str, str] = {}
    for s in program.get("sources") or []:
        if not isinstance(s, dict):
            continue
        u = str(s.get("url") or "")
        sid = str(s.get("source_id") or "")
        if u and sid:
            id_to_url[sid] = u
    ident = program.get("identity")
    if isinstance(ident, dict):
        for s in ident.get("sources") or []:
            if not isinstance(s, dict):
                continue
            u = str(s.get("url") or "")
            sid = str(s.get("source_id") or "")
            if u and sid:
                id_to_url[sid] = u
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
            if "source_url" in row:
                row.pop("source_id", None)
                continue
            sid = row.pop("source_id", None)
            if sid is not None:
                mapped = id_to_url.get(str(sid), str(sid) if sid else "")
                row["source_url"] = mapped


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
    hoist_curriculum_sources_and_derivation_notes_to_program(program)
    cur = program.get("curriculum")
    if isinstance(cur, dict):
        normalize_curriculum_electives(cur)


def coalesce_curriculum_subtree_from_llm(cur: dict[str, Any]) -> None:
    """
    Fix common LLM curriculum mistakes before JSON Schema validation.

    - Maps stray ``course_type`` → ``primary_type`` when needed and drops
      ``course_type`` (schema uses ``primary_type`` / ``secondary_type`` only).
    - If the model nested ``unit_system`` / ``sequencedness`` / ``curriculum_summary``
      inside a legacy ``derived_features`` blob, lifts them to the curriculum root
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
