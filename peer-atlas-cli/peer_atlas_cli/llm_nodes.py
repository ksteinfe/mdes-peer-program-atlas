"""Per-node LLM steps for program ingest."""

from __future__ import annotations

import copy
import json
import pathlib
from typing import Any

from peer_atlas_cli.categories import load_node_prompt_rules
from peer_atlas_cli.json_paths import set_path
from peer_atlas_cli.llm_client import LLMClient, parse_json_response
from peer_atlas_cli.program_sanitize import coalesce_curriculum_subtree_from_llm
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
    "verification",
)


def _node_prompt_rules_text(node_key: str, repo_root: pathlib.Path | None) -> str:
    root = repo_root
    if root is None:
        try:
            root = find_repo_root()
        except FileNotFoundError:
            return ""
    return load_node_prompt_rules(root, node_key)


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
        keys = set(parsed.keys())
        if keys != {node}:
            raise ValueError(
                f"LLM must return only top-level key {node!r}; got {sorted(keys)!r}"
            )
        subtree = parsed.get(node)
        if not isinstance(subtree, dict):
            raise ValueError(f"LLM value for {node!r} must be an object")
        if node == "curriculum":
            coalesce_curriculum_subtree_from_llm(subtree)
        program[node] = copy.deepcopy(subtree)

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
            f"Return ONLY a JSON object with the single top-level key {node!r} "
            "and a fixed subtree. Issues (fix all that apply):\n"
            + "\n".join(last_errors[:40])
        )


def run_curriculum_overview_step(
    *,
    client: LLMClient,
    program: dict[str, Any],
    evidence: str,
    categories_json: str,
    system: str = "You output only valid JSON. No prose.",
    repo_root: pathlib.Path | None = None,
    max_llm_attempts: int = 3,
) -> str:
    """
    First curriculum pass: LLM returns only top-level ``curriculum`` subtree
    (overview + placeholder core rows). Replaces ``program[\"curriculum\"]``.
    """
    tmpl = load_prompt("nodes/curriculum_overview.md")
    program_json = json.dumps(program, indent=2, ensure_ascii=False)
    base_user = render_template(
        tmpl,
        PROGRAM_JSON=program_json,
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
        keys = set(parsed.keys())
        if keys != {"curriculum"}:
            raise ValueError(
                "LLM must return only top-level key 'curriculum'; "
                f"got {sorted(keys)!r}"
            )
        subtree = parsed.get("curriculum")
        if not isinstance(subtree, dict):
            raise ValueError("LLM value for 'curriculum' must be an object")
        coalesce_curriculum_subtree_from_llm(subtree)
        program["curriculum"] = copy.deepcopy(subtree)

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
            "Return ONLY a JSON object with the single top-level key \"curriculum\" "
            "and a fixed subtree. Issues (fix all that apply):\n"
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
