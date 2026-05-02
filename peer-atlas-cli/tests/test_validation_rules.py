"""Extra validation rules."""

from __future__ import annotations

import json

from peer_atlas_cli.corpus_io import load_corpus
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus


def test_design_studio_requires_null_secondary() -> None:
    root = find_repo_root()
    corpus = json.loads(json.dumps(load_corpus(root)))
    bad = corpus["programs"][0]["curriculum"]["core_courses"][0]
    bad["primary_type"] = "design_studio"
    bad["secondary_type"] = "technology"
    errs = validate_corpus(root, corpus)
    assert any("design_studio" in e for e in errs)
