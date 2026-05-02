"""Normalize LLM-shaped program fragments before JSON Schema validation."""

from __future__ import annotations

from urllib.parse import urlparse

from typing import Any

_DERIVATION_SECTIONS = ("positioning", "duration", "degree_cost", "curriculum")


def normalize_sources(program: dict[str, Any]) -> int:
    """
    Ensure each source has only url, llm_title, llm_summary, retrieved_date.
    Drops legacy keys (direct_text, notes, source_id). Derives llm_title from the
    URL path when missing. Returns count of sources that gained a generated title.
    """
    fixed = 0
    sections = ("identity", "positioning", "duration", "degree_cost", "curriculum")
    for sec in sections:
        block = program.get(sec)
        if not isinstance(block, dict):
            continue
        srcs = block.get("sources")
        if not isinstance(srcs, list):
            continue
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
        block["sources"] = new_list
    return fixed


def normalize_derivation_notes(program: dict[str, Any], *, default_source_url: str) -> int:
    """
    Coerce derivation_notes entries that are bare strings into proper objects.
    Migrates legacy `source_id` keys to `source_url` on note dicts. Returns count fixed.
    """
    fixed = 0
    base = (default_source_url or "").strip()
    for sec in _DERIVATION_SECTIONS:
        block = program.get(sec)
        if not isinstance(block, dict):
            continue
        arr = block.get("derivation_notes")
        if not isinstance(arr, list):
            continue
        new_list: list[Any] = []
        for item in arr:
            if isinstance(item, str):
                new_list.append(
                    {
                        "derived_feature": "",
                        "source_url": base,
                        "note": item,
                    }
                )
                fixed += 1
            elif isinstance(item, dict):
                d = dict(item)
                if "source_id" in d and "source_url" not in d:
                    sid = d.pop("source_id", "")
                    d["source_url"] = str(sid) if sid else base
                    fixed += 1
                d.setdefault("derived_feature", "")
                d.setdefault("source_url", base)
                d.setdefault("note", "")
                if not isinstance(d.get("note"), str):
                    d["note"] = str(d.get("note", ""))
                new_list.append(d)
            else:
                new_list.append(item)
        block["derivation_notes"] = new_list
    return fixed


def strip_legacy_source_id_fields(program: dict[str, Any]) -> None:
    """Remove deprecated source_id from source objects (URL is the id)."""
    sections = ("identity", "positioning", "duration", "degree_cost", "curriculum")
    for sec in sections:
        block = program.get(sec)
        if not isinstance(block, dict):
            continue
        srcs = block.get("sources")
        if not isinstance(srcs, list):
            continue
        for s in srcs:
            if isinstance(s, dict) and "source_id" in s:
                s.pop("source_id", None)


def migrate_course_source_id_to_url(program: dict[str, Any]) -> None:
    """Map legacy curriculum source_id to source_url using identity.sources when possible."""
    ident = program.get("identity") or {}
    id_to_url: dict[str, str] = {}
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
        if row.get("primary_type") == "design_studio":
            row["secondary_type"] = None


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
            if isinstance(row, dict) and not (row.get("source_url") or "").strip():
                row["source_url"] = u
