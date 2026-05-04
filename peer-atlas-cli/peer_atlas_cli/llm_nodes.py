"""Per-node LLM steps for program ingest."""

from __future__ import annotations

import click
import copy
import json
import pathlib
import re
from typing import Any

import click

from peer_atlas_cli.categories import load_node_prompt_rules
from peer_atlas_cli.json_paths import set_path
from peer_atlas_cli.llm_client import LLMClient, parse_json_response
from peer_atlas_cli.program_sanitize import (
    coalesce_curriculum_subtree_from_llm,
    coerce_llm_rationale_object,
    hoist_nested_curriculum_llm_rationales,
)
from peer_atlas_cli.prompt_loader import load_prompt, render_template
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_single_program


def _validate_program_with_enum_repairs(
    repo_root: pathlib.Path, program: dict[str, Any]
) -> list[str]:
    notes: list[str] = []
    errs = validate_single_program(
        repo_root,
        program,
        category_repair_notes=notes,
        repair_invalid_enums=True,
    )
    for line in notes:
        click.echo(line, err=True)
    return errs


class LLMSchemaValidationError(Exception):
    """Raised when the merged program still fails JSON Schema after LLM retries."""

    def __init__(self, message: str, *, raw: str, errors: list[str]) -> None:
        super().__init__(message)
        self.raw = raw
        self.errors = errors


NODE_PROMPTS: dict[str, str] = {
    "positioning": "nodes/positioning.md",
    "duration": "nodes/duration.md",
    "degree_cost": "nodes/degree_cost.md",
    "curriculum": "nodes/curriculum.md",
    "identity": "nodes/identity.md",
    "verification": "nodes/verification.md",
}

INGEST_MAIN_NODES: tuple[str, ...] = (
    "positioning",
    "duration",
    "degree_cost",
    "curriculum_overview",
    "identity",
)


def run_search_context_from_seed(
    *,
    client: LLMClient,
    program: dict[str, Any],
    seed_markdown: str,
    seed_url: str,
    repo_root: pathlib.Path | None = None,
) -> None:
    """
    Populate ``program['atlas_search_context']`` from the CLI seed URL page (draft ingest).

    Used only to improve Tavily query strings; stripped before publish.
    """
    _ = repo_root
    tmpl = load_prompt("search_context_from_seed.md")
    md = (seed_markdown or "").strip()
    if len(md) > 120_000:
        md = md[:120_000] + "\n… [truncated for search-context prompt]\n"
    user = render_template(
        tmpl,
        SEED_URL=seed_url,
        SEED_PAGE_MARKDOWN=md,
        PROGRAM_CONTEXT_JSON=json.dumps(
            {
                "program_id": program.get("program_id"),
                "identity": program.get("identity"),
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    try:
        raw = client.complete(
            system="You output only valid JSON. No markdown fences, no commentary.",
            user=user,
            transcript_step="search-context-from-seed",
        )
    except Exception:
        return
    try:
        parsed = parse_json_response(raw)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(parsed, dict):
        return
    opl = parsed.get("official_program_label")
    si = parsed.get("short_institution")
    kws = parsed.get("degree_subject_keywords")
    ctx: dict[str, Any] = {}
    if isinstance(opl, str) and opl.strip():
        ctx["official_program_label"] = opl.strip()
    if isinstance(si, str) and si.strip():
        ctx["short_institution"] = si.strip()
    if isinstance(kws, list):
        cleaned = [str(x).strip() for x in kws if str(x).strip()]
        if cleaned:
            ctx["degree_subject_keywords"] = cleaned[:8]
    if ctx:
        program["atlas_search_context"] = ctx


def _node_prompt_rules_text(node_key: str, repo_root: pathlib.Path | None) -> str:
    root = repo_root
    if root is None:
        try:
            root = find_repo_root()
        except FileNotFoundError:
            return ""
    return load_node_prompt_rules(root, node_key)


def program_context_json_for_curriculum_steps(program: dict[str, Any]) -> str:
    """Minimal program slice for curriculum digest / overview prompts (no full PROGRAM_JSON)."""
    ident = program.get("identity")
    if not isinstance(ident, dict):
        ident = {}
    keys = (
        "institution_name",
        "program_name",
        "credential_name",
        "degree_type",
        "host_academic_units",
        "host_academic_model",
        "location_label",
    )
    ctx = {
        "program_id": program.get("program_id"),
        "base_url": program.get("base_url"),
        "identity": {k: ident.get(k) for k in keys},
    }
    return json.dumps(ctx, indent=2, ensure_ascii=False)


def _transcript_slug_for_source_url(url: str) -> str:
    from urllib.parse import urlparse

    tail = (urlparse(url).path or "").strip("/").replace("/", "-")
    if not tail:
        tail = "page"
    tail = re.sub(r"[^a-zA-Z0-9-]+", "-", tail).strip("-").lower()
    return tail[-48:] if tail else "page"


def program_context_json_for_course_patch(program: dict[str, Any], index: int) -> str:
    """Minimal program slice for per-core-course patch (no full PROGRAM_JSON)."""
    ident = program.get("identity")
    if not isinstance(ident, dict):
        ident = {}
    keys = (
        "institution_name",
        "program_name",
        "credential_name",
        "degree_type",
        "host_academic_units",
        "host_academic_model",
        "location_label",
    )
    cur = program.get("curriculum")
    if not isinstance(cur, dict):
        cur = {}
    core = cur.get("core_courses")
    row: dict[str, Any] = {}
    if isinstance(core, list) and 0 <= index < len(core) and isinstance(core[index], dict):
        row = copy.deepcopy(core[index])
    neighbors: list[dict[str, Any]] = []
    if isinstance(core, list):
        for j in (index - 1, index + 1):
            if 0 <= j < len(core) and isinstance(core[j], dict):
                neighbors.append(
                    {
                        "index": j,
                        "course_id": core[j].get("course_id"),
                        "course_title": core[j].get("course_title"),
                    }
                )
    ctx = {
        "program_id": program.get("program_id"),
        "base_url": program.get("base_url"),
        "identity": {k: ident.get(k) for k in keys},
        "curriculum": {
            "unit_system": cur.get("unit_system"),
            "sequencedness": cur.get("sequencedness"),
            "curriculum_summary": cur.get("curriculum_summary"),
            "offers_specialization": cur.get("offers_specialization"),
            "electives": copy.deepcopy(cur.get("electives"))
            if isinstance(cur.get("electives"), dict)
            else {"summary": "", "estimated_elective_course_count": None},
            "core_course_at_index": row,
            "neighbor_core_courses": neighbors,
        },
    }
    return json.dumps(ctx, indent=2, ensure_ascii=False)


def run_curriculum_digest_step(
    *,
    client: LLMClient,
    program_context_json: str,
    evidence: str,
    repo_root: pathlib.Path | None = None,
) -> str:
    """Prose-only digest of EVIDENCE (no fixed length); not wired into default ingest."""
    tmpl = load_prompt("nodes/curriculum_digest.md")
    user = render_template(
        tmpl,
        PROGRAM_CONTEXT_JSON=program_context_json,
        EVIDENCE=evidence,
        NODE_PROMPT_RULES=_node_prompt_rules_text("curriculum_digest", repo_root),
    )
    raw = client.complete(
        system="You write plain prose only. Do not output JSON or markdown code fences.",
        user=user,
        transcript_step="curriculum-digest",
    )
    return (raw or "").strip()


def run_curriculum_source_dense_extract_step(
    *,
    client: LLMClient,
    program_context_json: str,
    source_url: str,
    page_text: str,
    repo_root: pathlib.Path | None = None,
) -> str:
    """One LLM call: dense curriculum-related summary from a single fetched page."""
    tmpl = load_prompt("nodes/curriculum_source_extract.md")
    user = render_template(
        tmpl,
        PROGRAM_CONTEXT_JSON=program_context_json,
        SOURCE_URL=source_url,
        PAGE_TEXT=page_text,
        NODE_PROMPT_RULES=_node_prompt_rules_text(
            "curriculum_source_extract", repo_root
        ),
    )
    raw = client.complete(
        system="You write plain prose only. Do not output JSON or markdown code fences.",
        user=user,
        transcript_step=(
            f"curriculum-source-extract__{_transcript_slug_for_source_url(source_url)}"
        ),
    )
    return (raw or "").strip()


def run_node_step(
    *,
    client: LLMClient,
    program: dict[str, Any],
    node: str,
    evidence: str,
    categories_json: str,
    system: str = "You output only valid JSON. No prose.",
    repo_root: pathlib.Path | None = None,
    max_llm_attempts: int = 3,
) -> str:
    """
    Call LLM; expect a single top-level key matching `node`.
    Replace program[node] with parsed content. Returns raw assistant text from the
    successful attempt.

    When ``repo_root`` is set, validates the full program against the corpus schema
    after each merge and retries the LLM with schema error feedback up to
    ``max_llm_attempts`` times.
    """
    if node not in NODE_PROMPTS:
        raise ValueError(f"unknown ingest node: {node}")
    tmpl = load_prompt(NODE_PROMPTS[node])
    program_json = json.dumps(program, indent=2, ensure_ascii=False)
    base_user = render_template(
        tmpl,
        PROGRAM_JSON=program_json,
        EVIDENCE=evidence,
        CATEGORIES=categories_json,
        NODE_PROMPT_RULES=_node_prompt_rules_text(node, repo_root),
    )
    user = base_user
    last_raw = ""
    last_errors: list[str] = []

    for attempt in range(max(1, max_llm_attempts)):
        raw = client.complete(
            system=system,
            user=user,
            transcript_step=f"node-{node}",
        )
        last_raw = raw
        parsed = parse_json_response(raw)
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON must be an object")
        extra_notes = parsed.pop("llm_rationales", None)
        parsed.pop("derivation_notes", None)
        parsed.pop("sources", None)
        keys = set(parsed.keys())
        if keys != {node}:
            raise ValueError(
                f"LLM must return top-level key {node!r} (optional: llm_rationales); "
                f"got {sorted(keys)!r}"
            )
        subtree = parsed.get(node)
        if not isinstance(subtree, dict):
            raise ValueError(f"LLM value for {node!r} must be an object")
        if node == "curriculum":
            coalesce_curriculum_subtree_from_llm(subtree)
        program[node] = copy.deepcopy(subtree)
        if node == "curriculum":
            hoist_nested_curriculum_llm_rationales(program)
        if isinstance(extra_notes, list):
            arr = program.setdefault("llm_rationales", [])
            if isinstance(arr, list):
                base_u = str(program.get("base_url") or "").strip()
                for item in extra_notes:
                    if isinstance(item, dict):
                        coerced = coerce_llm_rationale_object(
                            item, default_source_url=base_u
                        )
                        if coerced is not None:
                            arr.append(coerced)

        if repo_root is None:
            return raw

        last_errors = _validate_program_with_enum_repairs(repo_root, program)
        if not last_errors:
            return raw

        if attempt + 1 >= max_llm_attempts:
            raise LLMSchemaValidationError(
                f"schema validation failed after {max_llm_attempts} LLM attempt(s)",
                raw=last_raw,
                errors=last_errors,
            )
        user = (
            base_user
            + "\n\nYour previous answer was rejected by the corpus JSON Schema. "
            f"Return a JSON object with top-level key {node!r} "
            "(and optional top-level \"llm_rationales\" array). "
            "Issues (fix all that apply):\n"
            + "\n".join(last_errors[:40])
        )


def run_curriculum_overview_step(
    *,
    client: LLMClient,
    program: dict[str, Any],
    evidence: str,
    categories_json: str,
    program_context_json: str,
    system: str = "You output only valid JSON. No prose.",
    repo_root: pathlib.Path | None = None,
    max_llm_attempts: int = 3,
) -> str:
    """
    First curriculum pass: LLM returns only top-level ``curriculum`` subtree
    (overview + placeholder core rows). Replaces ``program[\"curriculum\"]``.
    ``evidence`` is the in-memory per-URL extract mash (not persisted on the program).
    """
    tmpl = load_prompt("nodes/curriculum_overview.md")
    base_user = render_template(
        tmpl,
        PROGRAM_CONTEXT_JSON=program_context_json,
        EVIDENCE=evidence,
        CATEGORIES=categories_json,
        NODE_PROMPT_RULES=_node_prompt_rules_text(
            "curriculum_overview", repo_root
        ),
    )
    user = base_user
    last_raw = ""
    last_errors: list[str] = []

    for attempt in range(max(1, max_llm_attempts)):
        raw = client.complete(
            system=system,
            user=user,
            transcript_step="curriculum-overview",
        )
        last_raw = raw
        parsed = parse_json_response(raw)
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON must be an object")
        extra_notes = parsed.pop("llm_rationales", None)
        parsed.pop("derivation_notes", None)
        parsed.pop("sources", None)
        keys = set(parsed.keys())
        if keys != {"curriculum"}:
            raise ValueError(
                "LLM must return top-level key 'curriculum' (optional: llm_rationales); "
                f"got {sorted(keys)!r}"
            )
        subtree = parsed.get("curriculum")
        if not isinstance(subtree, dict):
            raise ValueError("LLM value for 'curriculum' must be an object")
        coalesce_curriculum_subtree_from_llm(subtree)
        program["curriculum"] = copy.deepcopy(subtree)
        hoist_nested_curriculum_llm_rationales(program)
        if isinstance(extra_notes, list):
            arr = program.setdefault("llm_rationales", [])
            if isinstance(arr, list):
                base_u = str(program.get("base_url") or "").strip()
                for item in extra_notes:
                    if isinstance(item, dict):
                        coerced = coerce_llm_rationale_object(
                            item, default_source_url=base_u
                        )
                        if coerced is not None:
                            arr.append(coerced)

        if repo_root is None:
            return raw

        last_errors = _validate_program_with_enum_repairs(repo_root, program)
        if not last_errors:
            return raw

        if attempt + 1 >= max_llm_attempts:
            raise LLMSchemaValidationError(
                f"schema validation failed after {max_llm_attempts} LLM attempt(s)",
                raw=last_raw,
                errors=last_errors,
            )
        user = (
            base_user
            + "\n\nYour previous answer was rejected by the corpus JSON Schema. "
            "Return a JSON object with top-level key \"curriculum\" "
            "(and optional top-level \"llm_rationales\" array). "
            "Issues (fix all that apply):\n"
            + "\n".join(last_errors[:40])
        )


def run_curriculum_course_patch(
    *,
    client: LLMClient,
    program: dict[str, Any],
    index: int,
    evidence: str,
    categories_json: str,
    system: str = "You output only valid JSON. No prose.",
    repo_root: pathlib.Path | None = None,
    max_llm_attempts: int = 3,
) -> str:
    """Apply {"updates":[{"path","value"},...]} for curriculum.core_courses.{index}.*"""
    tmpl = load_prompt("nodes/curriculum_course_patch.md")
    backup = copy.deepcopy(program)
    patch_ctx = program_context_json_for_course_patch(backup, index)
    base_user = render_template(
        tmpl,
        INDEX=str(index),
        PROGRAM_CONTEXT_FOR_PATCH=patch_ctx,
        EVIDENCE=evidence,
        CATEGORIES=categories_json,
        NODE_PROMPT_RULES=_node_prompt_rules_text(
            "curriculum_course_patch", repo_root
        ),
    )
    last_raw = ""
    last_errors: list[str] = []

    for attempt in range(max(1, max_llm_attempts)):
        if attempt > 0:
            program.clear()
            program.update(copy.deepcopy(backup))

        user = base_user
        if attempt > 0 and last_errors:
            user = (
                base_user
                + "\n\nYour previous patch left the program invalid under the corpus "
                "JSON Schema. Return an object with an **updates** array that fixes paths under "
                f"curriculum.core_courses.{index}.*. You may include top-level **llm_rationales**. Issues:\n"
                + "\n".join(last_errors[:40])
            )

        raw = client.complete(
            system=system,
            user=user,
            transcript_step=f"curriculum-course-patch__core-{index}",
        )
        last_raw = raw
        payload = parse_json_response(raw)
        if not isinstance(payload, dict):
            raise ValueError("patch payload must be an object")
        updates = payload.get("updates")
        if not isinstance(updates, list):
            raise ValueError("expected updates array")
        prefix = f"curriculum.core_courses.{index}."
        for u in updates:
            if not isinstance(u, dict):
                continue
            path = str(u.get("path", ""))
            if not path.startswith("curriculum.core_courses."):
                continue
            if not path.startswith(prefix):
                continue
            set_path(program, path, u.get("value"))

        extra_notes = payload.pop("llm_rationales", None)
        payload.pop("derivation_notes", None)
        payload.pop("sources", None)
        if isinstance(extra_notes, list):
            arr = program.setdefault("llm_rationales", [])
            if isinstance(arr, list):
                base_u = str(program.get("base_url") or "").strip()
                for item in extra_notes:
                    if isinstance(item, dict):
                        coerced = coerce_llm_rationale_object(
                            item, default_source_url=base_u
                        )
                        if coerced is not None:
                            arr.append(coerced)

        if repo_root is None:
            return raw

        last_errors = _validate_program_with_enum_repairs(repo_root, program)
        if not last_errors:
            return raw

        if attempt + 1 >= max_llm_attempts:
            raise LLMSchemaValidationError(
                f"schema validation failed after {max_llm_attempts} patch attempt(s) "
                f"(course index {index})",
                raw=last_raw,
                errors=last_errors,
            )
