"""program_context_json_for_course_patch — minimal patch payload."""

from __future__ import annotations

import json

from peer_atlas_cli.llm_nodes import program_context_json_for_course_patch


def test_program_context_json_for_course_patch_includes_row_and_neighbors() -> None:
    program = {
        "program_id": "p1",
        "base_url": "https://ex.edu/",
        "identity": {"institution_name": "Ex U", "program_name": "MDes"},
        "curriculum": {
            "unit_system": "semester_credit_hours",
            "sequencedness": "sequenced",
            "curriculum_summary": "Summary",
            "offers_specialization": False,
            "elective_requirements": "Pick 3",
            "core_courses": [
                {"course_id": "a", "course_title": "A"},
                {"course_id": "b", "course_title": "B"},
                {"course_id": "c", "course_title": "C"},
            ],
        },
    }
    raw = program_context_json_for_course_patch(program, 1)
    d = json.loads(raw)
    assert d["program_id"] == "p1"
    assert d["curriculum"]["core_course_at_index"]["course_id"] == "b"
    n = d["curriculum"]["neighbor_core_courses"]
    assert len(n) == 2
    assert {x["index"] for x in n} == {0, 2}
