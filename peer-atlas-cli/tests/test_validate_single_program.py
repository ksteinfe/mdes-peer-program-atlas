"""validate_single_program helper."""

from __future__ import annotations

from peer_atlas_cli.program_skeleton import (
    build_ingest_skeleton,
    set_ingest_stage,
    strip_atlas_ingest,
)
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_single_program


def test_validate_single_program_flags_bad_elective_shape() -> None:
    root = find_repo_root()
    program = build_ingest_skeleton("x", "https://example.edu/")
    set_ingest_stage(program, "complete")
    strip_atlas_ingest(program)
    program["curriculum"]["elective_courses"] = [
        {"course_id": "Open Elective", "units_or_credits": 3, "normalized_unit_weight": "not-a-number"}
    ]
    errs = validate_single_program(root, program)
    joined = " ".join(errs).lower()
    assert errs and ("elective" in joined or "normalized_unit_weight" in joined)
