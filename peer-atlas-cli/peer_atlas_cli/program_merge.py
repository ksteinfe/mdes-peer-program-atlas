"""Merge helpers for refresh / refine flows."""

from __future__ import annotations

import copy
from typing import Any

SOURCE_SECTIONS = ("identity", "positioning", "duration", "degree_cost", "curriculum")


def merge_sources_keep_existing(old: dict[str, Any], new: dict[str, Any]) -> None:
    for sec in SOURCE_SECTIONS:
        old_list = (old.get(sec) or {}).get("sources") if isinstance(old.get(sec), dict) else None
        new_sec = new.get(sec)
        if not isinstance(new_sec, dict):
            continue
        new_list = new_sec.get("sources") or []
        if not isinstance(old_list, list):
            old_list = []
        seen = {s.get("url") for s in old_list if isinstance(s, dict) and s.get("url")}
        merged = copy.deepcopy(old_list)
        for s in new_list:
            if not isinstance(s, dict):
                continue
            sc = {k: v for k, v in s.items() if k != "source_id"}
            u = sc.get("url")
            if u and u in seen:
                continue
            merged.append(copy.deepcopy(sc))
            if u:
                seen.add(u)
        if sec not in new or not isinstance(new[sec], dict):
            new[sec] = {}
        new[sec]["sources"] = merged


def apply_human_scope_preservation(
    old: dict[str, Any], merged: dict[str, Any], *, overwrite: bool
) -> None:
    if overwrite:
        return
    ver = old.get("verification") or {}
    if str(ver.get("status", "")) != "human_reviewed":
        return
    scope = ver.get("verification_scope") or []
    if not isinstance(scope, list):
        return
    for sec in scope:
        if isinstance(sec, str) and sec in old:
            merged[sec] = copy.deepcopy(old[sec])


def append_derivation_notes(program: dict[str, Any], notes: list[dict[str, Any]]) -> None:
    if not notes:
        return
    allowed = {"positioning", "duration", "degree_cost", "curriculum"}
    for raw in notes:
        if not isinstance(raw, dict):
            continue
        sec = str(raw.get("section", "")).strip()
        if sec not in allowed:
            sec = "curriculum"
        note = {k: v for k, v in raw.items() if k != "section"}
        if "source_id" in note and "source_url" not in note:
            note["source_url"] = str(note.pop("source_id", "") or "")
        if not all(k in note for k in ("derived_feature", "source_url", "note")):
            continue
        block = program.setdefault(sec, {})
        arr = block.setdefault("derivation_notes", [])
        if isinstance(arr, list):
            arr.append(copy.deepcopy(note))


def extend_fields_needing_review(program: dict[str, Any], paths: list[str]) -> None:
    ver = program.setdefault("verification", {})
    cur = ver.setdefault("fields_needing_review", [])
    if not isinstance(cur, list):
        ver["fields_needing_review"] = []
        cur = ver["fields_needing_review"]
    seen = set(str(x) for x in cur)
    for p in paths:
        ps = str(p)
        if ps not in seen:
            cur.append(ps)
            seen.add(ps)
