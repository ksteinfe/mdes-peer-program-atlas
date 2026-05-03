"""Load category vocabularies from categories_and_rules/*.json."""

from __future__ import annotations

import json
import pathlib
from typing import Any

CATEGORY_FILES = {
    "course_types": "course_types.json",
    "duration_categories": "duration_categories.json",
    "sequencedness": "sequencedness.json",
    "unit_systems": "unit_systems.json",
    "verification_statuses": "verification_statuses.json",
    "positioning_tags": "positioning_tags.json",
    "host_academic_models": "host_academic_models.json",
}

RULES_DIR = "categories_and_rules"
NODE_PROMPT_RULES_BUNDLE = "node_prompt_rules.json"


def load_categories(repo_root: pathlib.Path) -> dict[str, dict[str, Any]]:
    base = repo_root / RULES_DIR
    out: dict[str, dict[str, Any]] = {}
    for key, fname in CATEGORY_FILES.items():
        path = base / fname
        with path.open(encoding="utf-8") as f:
            out[key] = json.load(f)
    return out


def ids_for(category_key: str, categories: dict[str, dict[str, Any]]) -> set[str]:
    data = categories[category_key]
    items = data.get("items", [])
    return {str(it["id"]) for it in items if isinstance(it, dict) and "id" in it}


def categories_payload_for_prompt(categories: dict[str, dict[str, Any]]) -> str:
    return json.dumps(categories, indent=2, ensure_ascii=False)


def load_node_prompt_rules(repo_root: pathlib.Path, node_key: str) -> str:
    """Extra instructions for prompts/nodes/*.md from ``node_prompt_rules.json``.

    Top-level keys are ingest node names. Each value is an object with
    ``extra_instructions``: a JSON array of strings (joined with newlines for the
    prompt). A value may instead be a bare JSON array of strings. Missing node key,
    null, wrong type, or empty array yields an empty string.
    """
    path = repo_root / RULES_DIR / NODE_PROMPT_RULES_BUNDLE
    if not path.is_file():
        return ""
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    if not isinstance(bundle, dict):
        return ""
    block = bundle.get(node_key)
    extra: Any = None
    if isinstance(block, list):
        extra = block
    elif isinstance(block, dict):
        extra = block.get("extra_instructions")
    if extra is None:
        return ""
    if not isinstance(extra, list):
        return ""
    lines = [str(x).strip() for x in extra if str(x).strip()]
    return "\n".join(lines)
