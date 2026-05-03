"""Per-node LLM steps for program ingest."""

from __future__ import annotations

import copy
import json
import os
import pathlib
from collections.abc import Callable
from typing import Any

from peer_atlas_cli.categories import load_node_prompt_rules
from peer_atlas_cli.json_paths import set_path
from peer_atlas_cli.llm_client import LLMClient, parse_json_response
from peer_atlas_cli.program_sanitize import (
    coalesce_curriculum_subtree_from_llm,
    coerce_llm_rationale_object,
)
from peer_atlas_cli.prompt_loader import load_prompt, render_template
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_single_program


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


_CURRICULUM_EXTRACT_CONSOLE_PREVIEW = 12_000


def curriculum_source_extract_debug_full_user_message() -> bool:
    """When true, stderr debug prints the entire user message (can be very large)."""
    v = os.environ.get("PEER_ATLAS_CURRICULUM_EXTRACT_DEBUG", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def emit_curriculum_source_extract_llm_io(
    emit: Callable[[str], None],
    *,
    source_url: str,
    user_message: str,
    response: str,
) -> None:
    """Echo the exact user prompt sent to the LLM and the assistant reply (for ingest debug)."""
    full_user = curriculum_source_extract_debug_full_user_message()
    emit("=== curriculum_source_extract LLM I/O ===")
    emit(f"source: {source_url}")
    emit(
        f"user_message_chars={len(user_message)} assistant_chars={len(response)}; "
        "stderr always shows assistant response; user message is previewed unless "
        "PEER_ATLAS_CURRICULUM_EXTRACT_DEBUG=1"
    )
    if full_user or len(user_message) <= _CURRICULUM_EXTRACT_CONSOLE_PREVIEW:
        emit("--- user message (full) ---")
        emit(user_message)
    else:
        emit(
            f"--- user message (first {_CURRICULUM_EXTRACT_CONSOLE_PREVIEW} chars) ---"
        )
        emit(user_message[:_CURRICULUM_EXTRACT_CONSOLE_PREVIEW])
        emit(
            f"\n... [{len(user_message) - _CURRICULUM_EXTRACT_CONSOLE_PREVIEW} chars omitted; "
            "PEER_ATLAS_CURRICULUM_EXTRACT_DEBUG=1 prints full user message]\n"
        )
    emit("--- assistant response ---")
    emit(response if (response or "").strip() else "(empty)")
    emit("=== end curriculum_source_extract LLM I/O ===\n")


def run_curriculum_digest_step(
    *,
    client: LLMClient,
    program_context_json: str,
    evidence: str,
    repo_root: pathlib.Path | None = None,
) -> str:
    """Prose-only digest of EVIDENCE (no fixed length); stored as curriculum.evidence_curriculum_summary."""
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
    )
    return (raw or "").strip()


def run_curriculum_source_dense_extract_step(
    *,
    client: LLMClient,
    program_context_json: str,
    source_url: str,
    page_text: str,
    repo_root: pathlib.Path | None = None,
    emit_debug: Callable[[str], None] | None = None,
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
    )
    out = (raw or "").strip()
    if emit_debug is not None:
        emit_curriculum_source_extract_llm_io(
            emit_debug,
            source_url=source_url,
            user_message=user,
            response=out,
        )
    return out


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
        raw = client.complete(system=system, user=user)
        last_raw = raw
        parsed = parse_json_response(raw)
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON must be an object")
        extra_notes = parsed.pop("llm_rationales", None)
        if extra_notes is None:
            extra_notes = parsed.pop("derivation_notes", None)
        extra_sources = parsed.pop("sources", None)
        keys = set(parsed.keys())
        if keys != {node}:
            raise ValueError(
                f"LLM must return top-level key {node!r} (optional: llm_rationales, sources); "
                f"got {sorted(keys)!r}"
            )
        subtree = parsed.get(node)
        if not isinstance(subtree, dict):
            raise ValueError(f"LLM value for {node!r} must be an object")
        if node == "curriculum":
            coalesce_curriculum_subtree_from_llm(subtree)
        program[node] = copy.deepcopy(subtree)
        if isinstance(extra_sources, list):
            arr = program.setdefault("sources", [])
            if isinstance(arr, list):
                seen = {s.get("url") for s in arr if isinstance(s, dict)}
                for item in extra_sources:
                    if not isinstance(item, dict):
                        continue
                    u = item.get("url")
                    if u and u in seen:
                        continue
                    arr.append(copy.deepcopy(item))
                    if u:
                        seen.add(u)
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

        last_errors = validate_single_program(repo_root, program)
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
            "(and optional top-level \"llm_rationales\" / \"sources\" arrays). "
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
    curriculum_digest: str = "",
    evidence_curriculum_summary: str = "",
    system: str = "You output only valid JSON. No prose.",
    repo_root: pathlib.Path | None = None,
    max_llm_attempts: int = 3,
) -> str:
    """
    First curriculum pass: LLM returns only top-level ``curriculum`` subtree
    (overview + placeholder core rows). Replaces ``program[\"curriculum\"]``,
    then restores ``evidence_curriculum_summary`` from the per-source mash pipeline.
    """
    tmpl = load_prompt("nodes/curriculum_overview.md")
    digest_block = (curriculum_digest or "").strip() or "(no digest text; rely on EVIDENCE below.)"
    base_user = render_template(
        tmpl,
        PROGRAM_CONTEXT_JSON=program_context_json,
        CURRICULUM_DIGEST=digest_block,
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
        raw = client.complete(system=system, user=user)
        last_raw = raw
        parsed = parse_json_response(raw)
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON must be an object")
        extra_notes = parsed.pop("llm_rationales", None)
        if extra_notes is None:
            extra_notes = parsed.pop("derivation_notes", None)
        extra_sources = parsed.pop("sources", None)
        keys = set(parsed.keys())
        if keys != {"curriculum"}:
            raise ValueError(
                "LLM must return top-level key 'curriculum' (optional: llm_rationales, sources); "
                f"got {sorted(keys)!r}"
            )
        subtree = parsed.get("curriculum")
        if not isinstance(subtree, dict):
            raise ValueError("LLM value for 'curriculum' must be an object")
        coalesce_curriculum_subtree_from_llm(subtree)
        program["curriculum"] = copy.deepcopy(subtree)
        summary = (evidence_curriculum_summary or "").strip()
        program["curriculum"]["evidence_curriculum_summary"] = summary
        if isinstance(extra_sources, list):
            arr = program.setdefault("sources", [])
            if isinstance(arr, list):
                seen = {s.get("url") for s in arr if isinstance(s, dict)}
                for item in extra_sources:
                    if not isinstance(item, dict):
                        continue
                    u = item.get("url")
                    if u and u in seen:
                        continue
                    arr.append(copy.deepcopy(item))
                    if u:
                        seen.add(u)
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

        last_errors = validate_single_program(repo_root, program)
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
            "(and optional top-level \"llm_rationales\" / \"sources\" arrays). "
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
    program_json = json.dumps(program, indent=2, ensure_ascii=False)
    base_user = render_template(
        tmpl,
        INDEX=str(index),
        PROGRAM_JSON=program_json,
        EVIDENCE=evidence,
        CATEGORIES=categories_json,
        NODE_PROMPT_RULES=_node_prompt_rules_text(
            "curriculum_course_patch", repo_root
        ),
    )
    backup = copy.deepcopy(program)
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
                "JSON Schema. Return ONLY an updates array that fixes paths under "
                f"curriculum.core_courses.{index}.*. Issues:\n"
                + "\n".join(last_errors[:40])
            )

        raw = client.complete(system=system, user=user)
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

        if repo_root is None:
            return raw

        last_errors = validate_single_program(repo_root, program)
        if not last_errors:
            return raw

        if attempt + 1 >= max_llm_attempts:
            raise LLMSchemaValidationError(
                f"schema validation failed after {max_llm_attempts} patch attempt(s) "
                f"(course index {index})",
                raw=last_raw,
                errors=last_errors,
            )
