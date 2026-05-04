"""Merge helpers for corpus maintenance."""

from __future__ import annotations

import copy
from typing import Any

from peer_atlas_cli.program_sanitize import coerce_llm_rationale_object


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
        coerced = coerce_llm_rationale_object(note, default_source_url=base)
        if coerced is not None:
            arr.append(copy.deepcopy(coerced))
