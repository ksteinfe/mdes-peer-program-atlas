"""Build search queries per ingest node."""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

from peer_atlas_cli.categories import load_tavily_search_guidance

INGEST_NODE_ORDER = [
    "positioning",
    "duration",
    "degree_cost",
    "curriculum_overview",
    "identity",
]

_BUILTIN_GUIDANCE: dict[str, Any] = json.loads(
    r"""
{
  "schema_version": 1,
  "composition": {"fallback_label": "graduate design program"},
  "nodes": {
    "positioning": {"queries": ["{label} mission program overview"]},
    "duration": {"queries": ["{label} time to complete degree duration"]},
    "degree_cost": {"queries": ["{label} tuition fees cost"]},
    "curriculum": {"queries": ["{label} curriculum requirements"]},
    "curriculum_overview": {
      "queries": [
        "{label} degree plan curriculum map required courses by term",
        "{label} elective requirements"
      ]
    },
    "identity": {
      "queries": [
        "{label} official degree name credential",
        "{label} which college school department hosts program",
        "site:{seed_url} program"
      ],
      "skip_query_if_placeholder_empty": ["seed_url"]
    }
  },
  "curriculum_core_course": {
    "generic_placeholder_queries": [
      "{label} required course list degree requirements catalog"
    ],
    "queries": [
      "{label} {course_title} syllabus course description",
      "{label} {course_id} catalog"
    ],
    "append_when_seed_url": "{course_title} {institution} graduate course"
  }
}
"""
)


def _effective_guidance(
    repo_root: pathlib.Path | None, guidance: dict[str, Any] | None
) -> dict[str, Any]:
    if guidance is not None:
        return guidance
    if repo_root is not None:
        loaded = load_tavily_search_guidance(repo_root)
        if loaded:
            return loaded
    return _BUILTIN_GUIDANCE


def _inst_prog(program: dict[str, Any]) -> tuple[str, str]:
    ident = program.get("identity") or {}
    inst = str(ident.get("institution_name") or "").strip()
    pname = str(ident.get("program_name") or "").strip()
    return inst, pname


def _resolve_primary_label(
    program: dict[str, Any], user_query: str, guidance: dict[str, Any]
) -> str:
    comp = guidance.get("composition")
    if not isinstance(comp, dict):
        comp = {}
    fallback = str(comp.get("fallback_label") or "").strip() or "graduate design program"

    asc = program.get("atlas_search_context")
    if isinstance(asc, dict):
        opl = str(asc.get("official_program_label") or "").strip()
        if opl:
            return opl

    inst, pname = _inst_prog(program)
    joined = f"{inst} {pname}".strip()
    if joined:
        return joined
    uq = (user_query or "").strip()
    if uq:
        return uq
    return fallback


def _format_ctx(
    program: dict[str, Any],
    *,
    user_query: str,
    seed_url: str,
    label: str,
) -> dict[str, str]:
    inst, pname = _inst_prog(program)
    return {
        "label": label,
        "institution": inst,
        "program_name": pname,
        "seed_url": (seed_url or "").strip(),
    }


def _format_template(tmpl: str, ctx: dict[str, str]) -> str:
    out = tmpl
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", v)
    return " ".join(out.split()).strip()


def _queries_from_node_spec(
    node: str,
    node_spec: dict[str, Any],
    ctx: dict[str, str],
) -> list[str]:
    out: list[str] = []

    raw = node_spec.get("queries")
    if isinstance(raw, list):
        skip_empty = node_spec.get("skip_query_if_placeholder_empty")
        if not isinstance(skip_empty, list):
            skip_empty = []
        for t in raw:
            if not isinstance(t, str) or not t.strip():
                continue
            if "seed_url" in skip_empty and not ctx.get("seed_url"):
                if "{seed_url}" in t:
                    continue
            q = _format_template(t, ctx)
            if q:
                out.append(q)
    return out


def queries_for_node(
    node: str,
    program: dict[str, Any],
    *,
    seed_url: str,
    user_query: str,
    repo_root: pathlib.Path | None = None,
    guidance: dict[str, Any] | None = None,
) -> list[str]:
    g = _effective_guidance(repo_root, guidance)
    nodes = g.get("nodes")
    if not isinstance(nodes, dict):
        nodes = {}
    node_spec = nodes.get(node)
    if not isinstance(node_spec, dict):
        node_spec = {}

    label = _resolve_primary_label(program, user_query, g)
    ctx = _format_ctx(program, user_query=user_query, seed_url=seed_url, label=label)

    qs = _queries_from_node_spec(node, node_spec, ctx)
    if qs:
        return qs

    # Minimal fallback if JSON node block is empty
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
    user_query: str = "",
    repo_root: pathlib.Path | None = None,
    guidance: dict[str, Any] | None = None,
) -> list[str]:
    g = _effective_guidance(repo_root, guidance)
    cc = g.get("curriculum_core_course")
    if not isinstance(cc, dict):
        cc = _BUILTIN_GUIDANCE.get("curriculum_core_course") or {}

    label = _resolve_primary_label(program, user_query, g)
    inst, pname = _inst_prog(program)
    ct = (course_title or "").strip()
    cid = (course_id or "").strip()
    ctx = {
        "label": label,
        "institution": inst,
        "program_name": pname,
        "course_title": ct,
        "course_id": cid,
        "seed_url": (seed_url or "").strip(),
    }

    out: list[str] = []
    if _looks_like_generic_core_placeholder(ct, cid):
        gq = cc.get("generic_placeholder_queries")
        if isinstance(gq, list):
            for t in gq:
                if isinstance(t, str) and t.strip():
                    q = _format_template(t, ctx)
                    if q:
                        out.append(q)

    raw = cc.get("queries")
    if isinstance(raw, list) and raw:
        q1 = _format_template(str(raw[0]), ctx)
        q2: str
        if len(raw) >= 2 and cid:
            q2 = _format_template(str(raw[1]), ctx)
        else:
            q2 = q1
        for q in (q1, q2):
            if q:
                out.append(q)

    aw = cc.get("append_when_seed_url")
    if isinstance(aw, str) and aw.strip() and seed_url:
        q = _format_template(aw.strip(), ctx)
        if q:
            out.append(q)

    seen: set[str] = set()
    uniq: list[str] = []
    for q in out:
        q = (q or "").strip()
        if not q or q in seen:
            continue
        seen.add(q)
        uniq.append(q)
    return uniq
