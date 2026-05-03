"""Merge helpers for corpus maintenance (e.g. refresh-style source merges)."""

from __future__ import annotations

import copy
from typing import Any


def merge_sources_keep_existing(old: dict[str, Any], new: dict[str, Any]) -> None:
    """Merge URL-bibliography from ``old`` into ``new`` at program top-level ``sources``."""

    def collect_sources(prog: dict[str, Any]) -> list[Any]:
        out: list[Any] = []
        lst = prog.get("sources")
        if isinstance(lst, list):
            out.extend(lst)
        ident = prog.get("identity")
        if isinstance(ident, dict):
            alt = ident.get("sources")
            if isinstance(alt, list):
                out.extend(alt)
        return out

    old_list = collect_sources(old)
    new_list = new.get("sources")
    if not isinstance(new_list, list):
        new_list = []
    seen = {s.get("url") for s in new_list if isinstance(s, dict) and s.get("url")}
    merged = copy.deepcopy(new_list)
    for s in old_list:
        if not isinstance(s, dict):
            continue
        sc = {k: v for k, v in s.items() if k != "source_id"}
        u = sc.get("url")
        if u and u in seen:
            continue
        merged.append(copy.deepcopy(sc))
        if u:
            seen.add(u)
    new["sources"] = merged


def apply_human_scope_preservation(
    old: dict[str, Any], merged: dict[str, Any], *, overwrite: bool
) -> None:
    if overwrite:
        return
    ver = old.get("verification") or {}
    if str(ver.get("status", "")) != "human_reviewed":
        return
    scope = ver.get("verification_scope")
    if not isinstance(scope, list) or not scope:
        return
    for sec in scope:
        if isinstance(sec, str) and sec in old:
            merged[sec] = copy.deepcopy(old[sec])


def append_llm_rationales(program: dict[str, Any], notes: list[dict[str, Any]]) -> None:
    if not notes:
        return
    arr = program.setdefault("llm_rationales", [])
    if not isinstance(arr, list):
        program["llm_rationales"] = []
        arr = program["llm_rationales"]
    for raw in notes:
        if not isinstance(raw, dict):
            continue
        note = {k: v for k, v in raw.items() if k != "section"}
        if "source_id" in note and "source_url" not in note:
            note["source_url"] = str(note.pop("source_id", "") or "")
        if "feature" not in note and "derived_feature" in note:
            note["feature"] = str(note.pop("derived_feature", ""))
        if not all(k in note for k in ("feature", "source_url", "note")):
            continue
        arr.append(copy.deepcopy(note))


append_derivation_notes = append_llm_rationales
