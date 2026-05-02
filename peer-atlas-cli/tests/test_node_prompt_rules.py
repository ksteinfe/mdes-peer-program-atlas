"""node_prompt_rules.json (per-node extra_instructions)."""

from __future__ import annotations

from peer_atlas_cli.categories import load_node_prompt_rules
from peer_atlas_cli.repo_root import find_repo_root


def test_load_node_prompt_rules_joins_list_strings() -> None:
    root = find_repo_root()
    text = load_node_prompt_rules(root, "degree_cost")
    assert "derived_feature" in text
    assert "Totals and estimates" in text
    assert "defensible total" in text
    parts = text.split("\n")
    assert len(parts) >= 6
    assert all(p.strip() for p in parts)


def test_load_node_prompt_rules_empty_list() -> None:
    root = find_repo_root()
    assert load_node_prompt_rules(root, "identity") == ""


def test_load_node_prompt_rules_unknown_node() -> None:
    root = find_repo_root()
    assert load_node_prompt_rules(root, "nonexistent_node") == ""
