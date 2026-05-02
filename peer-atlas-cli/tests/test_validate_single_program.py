"""validate_single_program helper."""

from __future__ import annotations

from peer_atlas_cli.program_skeleton import build_ingest_skeleton, set_ingest_stage
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_single_program


def test_validate_single_program_flags_bad_elective_shape() -> None:
    root = find_repo_root()
    program = build_ingest_skeleton("x", "https://example.edu/")
    set_ingest_stage(program, "curriculum")
    program["curriculum"]["elective_requirements"] = [
        {"requirement_type": "x", "count": 1, "description": "d", "allowed_types": []}
    ]
    errs = validate_single_program(root, program)
    assert any("elective_requirements" in e for e in errs)
