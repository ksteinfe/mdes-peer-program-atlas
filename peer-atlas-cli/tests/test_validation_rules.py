"""Extra validation rules."""

from __future__ import annotations

import json

from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus

from tests.corpus_fixtures import minimal_valid_corpus


def test_design_studio_requires_null_secondary() -> None:
    root = find_repo_root()
    corpus = json.loads(json.dumps(minimal_valid_corpus()))
    bad = corpus["programs"][0]["curriculum"]["core_courses"][0]
    bad["primary_type"] = "design_studio"
    bad["secondary_type"] = "technology"
    errs = validate_corpus(
        root, corpus, repair_invalid_enums=True, category_repair_notes=[]
    )
    assert errs == []
    assert bad["secondary_type"] is None
