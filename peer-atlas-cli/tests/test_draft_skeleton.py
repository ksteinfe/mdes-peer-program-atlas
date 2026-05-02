"""Draft ingest skeleton validation."""

from __future__ import annotations

from peer_atlas_cli.identity_fallback import apply_identity_fallbacks
from peer_atlas_cli.program_skeleton import build_ingest_skeleton
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import (
    program_uses_draft_validation,
    validate_program_categories,
    validate_program_shape,
    load_categories,
)


def test_skeleton_is_draft_and_validates() -> None:
    root = find_repo_root()
    p = build_ingest_skeleton("test_skeleton_id", "https://example.edu/")
    assert program_uses_draft_validation(p) is True
    apply_identity_fallbacks(p, url="", query="Example Univ MDes")
    cats = load_categories(root)
    assert validate_program_shape(root, p) == []
    assert validate_program_categories(p, cats, draft=True) == []
