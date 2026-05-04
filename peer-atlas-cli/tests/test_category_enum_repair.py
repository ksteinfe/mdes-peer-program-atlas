"""Category enum repair (INVALID sentinel)."""

from __future__ import annotations

import json

from peer_atlas_cli.categories import load_categories
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import repair_invalid_category_enums, validate_corpus

from tests.corpus_fixtures import minimal_valid_corpus


def test_repair_maps_unknown_course_type_to_invalid() -> None:
    root = find_repo_root()
    cats = load_categories(root)
    corpus = json.loads(json.dumps(minimal_valid_corpus()))
    row = corpus["programs"][0]["curriculum"]["core_courses"][0]
    row["primary_type"] = "technology"
    row["secondary_type"] = "not_a_real_type"
    notes = repair_invalid_category_enums(corpus["programs"][0], cats)
    assert any("secondary_type" in n and "not_a_real_type" in n for n in notes)
    assert row["secondary_type"] == "INVALID"


def test_repair_open_or_other_secondary_becomes_invalid_then_cleared_for_studio() -> None:
    root = find_repo_root()
    cats = load_categories(root)
    corpus = json.loads(json.dumps(minimal_valid_corpus()))
    row = corpus["programs"][0]["curriculum"]["core_courses"][0]
    row["primary_type"] = "design_studio"
    row["secondary_type"] = "open_or_other"
    row["normalized_unit_weight"] = 2.0
    repair_invalid_category_enums(corpus["programs"][0], cats)
    assert row["secondary_type"] is None


def test_validate_corpus_with_repair_passes_after_bad_tag() -> None:
    root = find_repo_root()
    corpus = json.loads(json.dumps(minimal_valid_corpus()))
    corpus["programs"][0]["positioning"]["positioning_tags"] = ["professional", "bogus_tag"]
    errs = validate_corpus(root, corpus, repair_invalid_enums=True)
    assert errs == []
    assert corpus["programs"][0]["positioning"]["positioning_tags"] == [
        "professional",
        "INVALID",
    ]
