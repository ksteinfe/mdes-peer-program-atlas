"""validate + merge-patch."""

from __future__ import annotations

import json

from peer_atlas_cli.commands.merge_patch import apply_merge_patch_to_corpus
from peer_atlas_cli.corpus_io import load_corpus
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus

from tests.corpus_fixtures import minimal_valid_corpus


def test_validate_corpus_clean() -> None:
    root = find_repo_root()
    corpus = load_corpus(root)
    assert validate_corpus(root, corpus) == []


def test_validate_duplicate_program_id() -> None:
    root = find_repo_root()
    corpus = minimal_valid_corpus()
    dup = json.loads(json.dumps(corpus["programs"][0]))
    corpus["programs"].append(dup)
    errs = validate_corpus(root, corpus)
    assert any("duplicate program_id" in e for e in errs)


def test_apply_merge_patch_in_memory() -> None:
    root = find_repo_root()
    corpus = json.loads(json.dumps(minimal_valid_corpus()))
    pid = corpus["programs"][0]["program_id"]
    old_status = corpus["programs"][0]["verification"]["status"]
    patch = {
        "patch_metadata": {
            "created_at": "2099-01-01",
            "created_by": "test",
            "source_corpus_name": "MDes Peer Program Comparator Corpus",
        },
        "changes": [
            {
                "program_id": pid,
                "path": "verification.status",
                "old_value": old_status,
                "new_value": "human_reviewed",
            }
        ],
    }
    applied = apply_merge_patch_to_corpus(
        corpus,
        patch,
        repo_root=root,
        allow_new_paths=False,
        skip_old_check=False,
    )
    assert applied == [(pid, "verification.status")]
    assert corpus["programs"][0]["verification"]["status"] == "human_reviewed"
    assert validate_corpus(root, corpus) == []
