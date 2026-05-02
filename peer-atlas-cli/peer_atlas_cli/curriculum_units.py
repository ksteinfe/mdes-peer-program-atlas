"""Compute normalized_unit_weight for core courses and elective slots."""

from __future__ import annotations

from statistics import mean
from typing import Any


def recompute_normalized_unit_weights(program: dict[str, Any]) -> None:
    cur = program.get("curriculum") or {}
    units: list[float] = []
    for c in cur.get("core_courses") or []:
        u = c.get("units_or_credits")
        if isinstance(u, (int, float)):
            units.append(float(u))
    for e in cur.get("elective_courses") or []:
        u = e.get("units_or_credits")
        if isinstance(u, (int, float)):
            units.append(float(u))
    if not units:
        for c in cur.get("core_courses") or []:
            c["normalized_unit_weight"] = None
        for e in cur.get("elective_courses") or []:
            e["normalized_unit_weight"] = None
        return
    avg = mean(units)
    if avg == 0:
        for c in cur.get("core_courses") or []:
            c["normalized_unit_weight"] = None
        for e in cur.get("elective_courses") or []:
            e["normalized_unit_weight"] = None
        return
    for c in cur.get("core_courses") or []:
        u = c.get("units_or_credits")
        if isinstance(u, (int, float)):
            c["normalized_unit_weight"] = float(u) / avg
        else:
            c["normalized_unit_weight"] = None
    for e in cur.get("elective_courses") or []:
        u = e.get("units_or_credits")
        if isinstance(u, (int, float)):
            e["normalized_unit_weight"] = float(u) / avg
        else:
            e["normalized_unit_weight"] = None
