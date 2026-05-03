"""Compute normalized_unit_weight for core courses."""

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
    if not units:
        for c in cur.get("core_courses") or []:
            c["normalized_unit_weight"] = None
        return
    avg = mean(units)
    if avg == 0:
        for c in cur.get("core_courses") or []:
            c["normalized_unit_weight"] = None
        return
    for c in cur.get("core_courses") or []:
        u = c.get("units_or_credits")
        if isinstance(u, (int, float)):
            c["normalized_unit_weight"] = float(u) / avg
        else:
            c["normalized_unit_weight"] = None
