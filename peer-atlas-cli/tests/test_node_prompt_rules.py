"""node_prompt_rules.json (per-node extra_instructions)."""

from __future__ import annotations

from peer_atlas_cli.categories import load_node_prompt_rules
from peer_atlas_cli.repo_root import find_repo_root


def test_load_node_prompt_rules_joins_list_strings() -> None:
    root = find_repo_root()
    text = load_node_prompt_rules(root, "degree_cost")
    assert "feature" in text
    assert "comparison_cost_usd" in text
    assert "total_degree_cost_base_currency" in text
    parts = text.split("\n")
    assert len(parts) >= 4
    assert all(p.strip() for p in parts)


def test_load_node_prompt_rules_empty_list() -> None:
    root = find_repo_root()
    assert load_node_prompt_rules(root, "identity") == ""


def test_load_node_prompt_rules_curriculum_overview_nonempty() -> None:
    root = find_repo_root()
    text = load_node_prompt_rules(root, "curriculum_overview")
    assert "core_courses" in text
    assert "elective" in text.lower()
    parts = [p for p in text.split("\n") if p.strip()]
    assert len(parts) >= 6


def test_load_node_prompt_rules_curriculum_digest_nonempty() -> None:
    root = find_repo_root()
    text = load_node_prompt_rules(root, "curriculum_digest")
    assert "evidence" in text.lower()
    assert "elective" in text.lower()


def test_load_node_prompt_rules_curriculum_source_extract_nonempty() -> None:
    root = find_repo_root()
    text = load_node_prompt_rules(root, "curriculum_source_extract")
    assert "curriculum" in text.lower()
    assert "course" in text.lower()
    parts = [p for p in text.split("\n") if p.strip()]
    assert len(parts) >= 4
