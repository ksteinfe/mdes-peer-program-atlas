"""Build search queries per ingest node."""

from __future__ import annotations

import re
from typing import Any

INGEST_NODE_ORDER = [
    "positioning",
    "duration",
    "degree_cost",
    "curriculum_overview",
    "identity",
]


def _inst_prog(program: dict[str, Any]) -> tuple[str, str]:
    ident = program.get("identity") or {}
    inst = str(ident.get("institution_name") or "").strip()
    pname = str(ident.get("program_name") or "").strip()
    return inst, pname


def queries_for_node(
    node: str,
    program: dict[str, Any],
    *,
    seed_url: str,
    user_query: str,
) -> list[str]:
    inst, pname = _inst_prog(program)
    label = f"{inst} {pname}".strip() or (user_query or "").strip() or "graduate design program"
    u = (seed_url or "").strip()

    if node == "positioning":
        return [
            f"{label} mission program overview"
        ]
    if node == "duration":
        return [
            f"{label} time to complete degree duration"
        ]
    if node == "degree_cost":
        return [
            f"{inst} tuition fees cost" if inst else f"{label} tuition fees cost"
        ]
    if node == "curriculum":
        return [
            f"{label} curriculum requirements"
        ]
    if node == "curriculum_overview":
        return [
            f"{label} degree plan curriculum map required courses by term",
            f"{label} program structure class sequence",
            f"{label} elective requirements"
        ]
    if node == "identity":
        return [
            f"{label} official degree name credential",
            f"{label} which college school department hosts program",
            *([f"site:{u} program"] if u else []),
        ]
    return [label]


def _looks_like_generic_core_placeholder(course_title: str, course_id: str) -> bool:
    """True when overview left a vague label — Tavily needs degree-plan queries, not 'Core course 2'."""
    t = (course_title or "").strip().lower()
    if "placeholder" in t:
        return True
    if re.match(r"^core course \d+$", t):
        return True
    if re.match(r"^course \d+$", t):
        return True
    return False


def queries_for_core_course(
    program: dict[str, Any],
    course_title: str,
    course_id: str,
    *,
    seed_url: str,
) -> list[str]:
    inst, pname = _inst_prog(program)
    base = f"{inst} {pname}".strip()
    ct = (course_title or "").strip()
    cid = (course_id or "").strip()
    q1 = f"{base} {ct} syllabus course description".strip()
    q2 = f"{base} {cid} catalog".strip() if cid else q1
    out: list[str] = []
    if _looks_like_generic_core_placeholder(ct, cid):
        label = f"{inst} {pname}".strip() or pname or inst
        out.extend(
            [
                f"{label} required core courses degree requirements catalog",
                f"{label} core curriculum course list units",
                f"{label} first year core information courses".strip(),
            ]
        )
    out.extend([q1, q2])
    if seed_url:
        out.append(f"{ct} {inst} graduate course".strip())
    # Dedupe while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for q in out:
        q = (q or "").strip()
        if not q or q in seen:
            continue
        seen.add(q)
        uniq.append(q)
    return uniq
