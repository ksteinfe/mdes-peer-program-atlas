"""Merge helpers for corpus maintenance (e.g. refresh-style bibliography merges)."""

from __future__ import annotations

import copy
from typing import Any

from peer_atlas_cli.program_sanitize import (
    bibliography_dict_to_rationale,
    coerce_llm_rationale_object,
)


def merge_sources_keep_existing(old: dict[str, Any], new: dict[str, Any]) -> None:
    """
    Append legacy bibliography from ``old`` (top-level ``sources`` or
    ``identity.sources``) as ``llm_rationales`` rows on ``new``.
    """

    def collect_biblio(prog: dict[str, Any]) -> list[Any]:
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

    old_list = collect_biblio(old)
    if not old_list:
        return
    arr = new.setdefault("llm_rationales", [])
    if not isinstance(arr, list):
        new["llm_rationales"] = []
        arr = new["llm_rationales"]
    seen_urls = {
        str(r.get("source_url") or "").strip() for r in arr if isinstance(r, dict)
    }
    for s in old_list:
        if not isinstance(s, dict):
            continue
        sc = {k: v for k, v in s.items() if k != "source_id"}
        r = bibliography_dict_to_rationale(sc, feature="program.citation")
        u = r["source_url"]
        if u and u in seen_urls:
            continue
        if u:
            seen_urls.add(u)
        arr.append(r)


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
    base = str(program.get("base_url") or "").strip()
    for raw in notes:
        if not isinstance(raw, dict):
            continue
        note = {k: v for k, v in raw.items() if k != "section"}
        if "source_id" in note and "source_url" not in note:
            note["source_url"] = str(note.pop("source_id", "") or "")
        if "feature" not in note and "derived_feature" in note:
            note["feature"] = str(note.pop("derived_feature", ""))
        coerced = coerce_llm_rationale_object(note, default_source_url=base)
        if coerced is not None:
            arr.append(copy.deepcopy(coerced))


append_derivation_notes = append_llm_rationales
