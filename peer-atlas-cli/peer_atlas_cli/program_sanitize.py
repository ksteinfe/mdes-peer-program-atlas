"""Normalize LLM-shaped program fragments before JSON Schema validation."""

from __future__ import annotations

from urllib.parse import urlparse

from typing import Any

_LEGACY_FEATURE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("duration.derived_features.", "duration."),
    ("degree_cost.derived_features.", "degree_cost."),
    ("curriculum.derived_features.", "curriculum."),
)


def _upgrade_feature_path(s: str) -> str:
    out = str(s or "")
    for old, new in _LEGACY_FEATURE_PREFIXES:
        out = out.replace(old, new)
    return out


def migrate_record_canonical_shape(program: dict[str, Any]) -> None:
    """
    In-place migration: ``derivation_notes`` → ``llm_rationales`` (``feature`` key),
    ``identity.sources`` → top-level ``sources``, flatten ``derived_features`` on nodes.
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

    root_src = program.get("sources")
    if not isinstance(root_src, list):
        program["sources"] = []
        root_src = program["sources"]

    ident = program.get("identity")
    if isinstance(ident, dict) and "sources" in ident:
        legacy_src = ident.pop("sources")
        if isinstance(legacy_src, list):
            seen = {s.get("url") for s in root_src if isinstance(s, dict)}
            for s in legacy_src:
                if not isinstance(s, dict):
                    continue
                u = s.get("url")
                if u and u not in seen:
                    root_src.append(dict(s))
                    seen.add(u)

    program.setdefault("sources", [])

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
    _hoist_derived_features(
        program,
        "curriculum",
        ("unit_system", "sequencedness", "curriculum_summary"),
    )


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
    root_src = program.get("sources")
    if not isinstance(root_src, list):
        program["sources"] = []
        root_src = program["sources"]

    ident = program.setdefault("identity", {})
    if not isinstance(ident, dict):
        program["identity"] = {}
        ident = program["identity"]

    for sec in ("positioning", "duration", "degree_cost", "curriculum"):
        block = program.get(sec)
        if not isinstance(block, dict):
            continue
        for nk in ("llm_rationales", "derivation_notes"):
            nested = block.pop(nk, None)
            if isinstance(nested, list):
                root_lr.extend(nested)
        srcs = block.pop("sources", None)
        if isinstance(srcs, list) and srcs:
            seen = {s.get("url") for s in root_src if isinstance(s, dict)}
            for s in srcs:
                if not isinstance(s, dict):
                    continue
                u = s.get("url")
                if u and u not in seen:
                    root_src.append(dict(s))
                    seen.add(u)

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
        for k in (
            "has_required_core",
            "has_structured_electives",
            "has_open_electives",
            "has_required_studio_sequence",
            "has_required_thesis_or_capstone",
            "has_internship_or_professional_practice_requirement",
            "total_units_or_credits",
        ):
            cur.pop(k, None)
        if "offers_specialization" not in cur:
            cur["offers_specialization"] = False
        elif cur.get("offers_specialization") is not None and not isinstance(
            cur.get("offers_specialization"), bool
        ):
            cur["offers_specialization"] = False
        cur.pop("evidence_curriculum_summary", None)


def normalize_sources(program: dict[str, Any]) -> int:
    """
    Ensure each top-level source has only url, llm_title, llm_summary, retrieved_date.
    Drops legacy keys (direct_text, notes, source_id). Derives llm_title from the
    URL path when missing. Returns count of sources that gained a generated title.
    """
    fixed = 0
    migrate_record_canonical_shape(program)
    srcs = program.get("sources")
    if not isinstance(srcs, list):
        return fixed
    new_list: list[Any] = []
    for s in srcs:
        if not isinstance(s, dict):
            new_list.append(s)
            continue
        d = dict(s)
        d.pop("direct_text", None)
        d.pop("notes", None)
        d.pop("source_id", None)
        url = str(d.get("url") or "").strip()
        title = str(d.get("llm_title") or "").strip()
        if url and not title:
            path = [p for p in urlparse(url).path.strip("/").split("/") if p]
            tail = path[-1].replace("-", " ").replace("_", " ") if path else "home"
            title = (tail[:1].upper() + tail[1:120]) if tail else "Web source"
            fixed += 1
        summ = d.get("llm_summary")
        if summ is None:
            summ_s = ""
        else:
            summ_s = str(summ)
        rd = d.get("retrieved_date")
        if rd is None:
            rd_s = ""
        else:
            rd_s = str(rd)
        new_list.append(
            {
                "url": url,
                "llm_title": title[:200] if title else "",
                "llm_summary": summ_s,
                "retrieved_date": rd_s,
            }
        )
    program["sources"] = new_list
    return fixed


def coerce_llm_rationale_object(
    item: dict[str, Any],
    *,
    default_source_url: str = "",
) -> dict[str, Any] | None:
    """
    Map LLM / legacy keys onto the corpus ``llmRationale`` shape: only ``feature``,
    ``source_url``, and ``note`` (no ``rationale``, ``reason``, etc.).
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
    su = d.get("source_url")
    if su is None or (isinstance(su, str) and not su.strip()):
        su = d.get("url") or base
    if su is not None and not isinstance(su, str):
        su = str(su)
    return {
        "feature": "" if feat is None else str(feat),
        "source_url": str(su).strip() if su else "",
        "note": "" if note is None else str(note).strip(),
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
            new_list.append(
                {
                    "feature": "",
                    "source_url": base,
                    "note": item,
                }
            )
            fixed += 1
        elif isinstance(item, dict):
            coerced = coerce_llm_rationale_object(item, default_source_url=base)
            if coerced is not None:
                if set(item.keys()) - {"feature", "source_url", "note"}:
                    fixed += 1
                new_list.append(coerced)
        else:
            new_list.append(item)
    program["llm_rationales"] = new_list
    return fixed


# Backwards-compatible name for callers/tests
normalize_derivation_notes = normalize_llm_rationales


def strip_legacy_source_id_fields(program: dict[str, Any]) -> None:
    """Remove deprecated source_id from top-level source objects (URL is the id)."""
    migrate_record_canonical_shape(program)
    srcs = program.get("sources")
    if not isinstance(srcs, list):
        return
    for s in srcs:
        if isinstance(s, dict) and "source_id" in s:
            s.pop("source_id", None)


def migrate_course_source_id_to_url(program: dict[str, Any]) -> None:
    """Map legacy curriculum source_id to source_url using program.sources when possible."""
    migrate_record_canonical_shape(program)
    id_to_url: dict[str, str] = {}
    for s in program.get("sources") or []:
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


def normalize_curriculum_electives(cur: dict[str, Any]) -> None:
    """
    Ensure curriculum uses ``elective_requirements`` (string) + ``elective_courses`` (array).

    Migrates legacy ``elective_requirements`` as an array of structured objects into
    a human-readable string plus simplified ``elective_courses`` rows.
    """
    if not isinstance(cur, dict):
        return
    er = cur.get("elective_requirements")
    if isinstance(er, list):
        texts: list[str] = []
        slots: list[dict[str, Any]] = []
        for row in er:
            if not isinstance(row, dict):
                continue
            name = str(row.get("requirement_name") or "").strip()
            desc = str(row.get("requirement_description") or "").strip()
            summ = str(row.get("course_summary") or "").strip()
            if name and desc:
                texts.append(f"{name}: {desc}")
            elif name:
                texts.append(name)
            elif desc:
                texts.append(desc)
            elif summ:
                texts.append(summ)
            cid = (
                name
                or str(row.get("primary_type") or "").strip()
                or "Elective"
            )[:200]
            u = row.get("units_or_credits")
            nu = row.get("normalized_unit_weight")
            slots.append(
                {
                    "course_id": cid or "Elective",
                    "units_or_credits": u
                    if isinstance(u, (int, float))
                    else None,
                    "normalized_unit_weight": nu
                    if isinstance(nu, (int, float))
                    else None,
                }
            )
        cur["elective_requirements"] = "; ".join(texts) if texts else ""
        cur["elective_courses"] = slots
    elif isinstance(er, str):
        if not isinstance(cur.get("elective_courses"), list):
            cur["elective_courses"] = []
    else:
        cur["elective_requirements"] = ""
        if not isinstance(cur.get("elective_courses"), list):
            cur["elective_courses"] = []
    ec = cur.get("elective_courses")
    if not isinstance(ec, list):
        cur["elective_courses"] = []
        ec = cur["elective_courses"]
    for row in ec:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("course_id") or "Elective").strip()[:200] or "Elective"
        row["course_id"] = cid
        row.setdefault("units_or_credits", None)
        row.setdefault("normalized_unit_weight", None)
    if not isinstance(cur.get("elective_requirements"), str):
        cur["elective_requirements"] = ""


def normalize_curriculum_electives_in_program(program: dict[str, Any]) -> None:
    cur = program.get("curriculum")
    if isinstance(cur, dict):
        normalize_curriculum_electives(cur)


def coalesce_curriculum_subtree_from_llm(cur: dict[str, Any]) -> None:
    """
    Fix common LLM curriculum mistakes before JSON Schema validation.

    - Maps stray ``course_type`` → ``primary_type`` when needed and drops
      ``course_type`` (schema uses ``primary_type`` / ``secondary_type`` only).
    - Migrates / normalizes electives (``elective_requirements`` string +
      ``elective_courses`` array).
    - Ensures required nullable keys exist on ``core_courses`` rows.
    """
    if not isinstance(cur, dict):
        return
    cur.pop("evidence_curriculum_summary", None)
    df = cur.get("derived_features")
    if isinstance(df, dict):
        for k in ("unit_system", "sequencedness", "curriculum_summary"):
            if k in df:
                cur[k] = df[k]
        cur.pop("derived_features", None)
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
    if not isinstance(ospec, bool):
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
