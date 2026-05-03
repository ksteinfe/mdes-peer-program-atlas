"""validate_single_program helper."""

from __future__ import annotations

from peer_atlas_cli.program_skeleton import (
    build_ingest_skeleton,
    set_ingest_stage,
    strip_atlas_ingest,
)
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_single_program


def test_validate_single_program_flags_bad_electives_count_type() -> None:
    root = find_repo_root()
    program = build_ingest_skeleton("x", "https://example.edu/")
    set_ingest_stage(program, "complete")
    strip_atlas_ingest(program)
    program["curriculum"]["electives"]["estimated_elective_course_count"] = "not-an-int"
    errs = validate_single_program(root, program)
    joined = " ".join(errs).lower()
    assert errs and ("electives" in joined or "estimated_elective_course_count" in joined)


def test_strip_atlas_ingest_removes_search_context() -> None:
    program = build_ingest_skeleton("x", "https://example.edu/")
    program["atlas_search_context"] = {"official_program_label": "Test"}
    strip_atlas_ingest(program)
    assert "atlas_search_context" not in program
    assert "atlas_ingest" not in program
