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
    for key in ("core_courses", "elective_requirements"):
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


def ensure_course_source_urls(program: dict[str, Any], base_url: str) -> None:
    """Set missing curriculum row source_url to program base_url (draft-friendly)."""
    u = (base_url or "").strip()
    if not u:
        return
    cur = program.get("curriculum")
    if not isinstance(cur, dict):
        return
    for key in ("core_courses", "elective_requirements"):
        rows = cur.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and not (row.get("source_url") or "").strip():
                row["source_url"] = u
