"""Build search queries per ingest node."""

from __future__ import annotations

from typing import Any

INGEST_NODE_ORDER = [
    "positioning",
    "duration",
    "degree_cost",
    "curriculum",
    "identity",
    "verification",
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
            f"{label} program positioning mission interdisciplinary",
            f"{label} MDes design graduate focus areas",
            f"{label} official program overview",
        ]
    if node == "duration":
        return [
            f"{label} degree length semesters credits duration",
            f"{label} time to complete graduate program",
            f"{label} academic calendar length",
        ]
    if node == "degree_cost":
        return [
            f"{label} tuition fees cost graduate",
            f"{label} estimated cost of attendance",
            f"{inst} graduate tuition" if inst else f"{label} tuition",
        ]
    if node == "curriculum":
        return [
            f"{label} curriculum required courses core",
            f"{label} MDes course requirements catalog",
            f"{label} studio thesis credits units",
        ]
    if node == "identity":
        return [
            f"{label} official degree name credential",
            f"{label} which college school department hosts program",
            f"{label} location campus",
            *( [f"site:{u} program"] if u else [] ),
        ]
    if node == "verification":
        return [
            f"{label} official admissions program page",
            f"{inst} graduate program handbook" if inst else f"{label} handbook",
        ]
    return [label]


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
    out = [q1, q2]
    if seed_url:
        out.append(f"{ct} {inst} graduate course".strip())
    return [q for q in out if q]
