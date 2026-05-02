"""query_builders."""

from __future__ import annotations

from peer_atlas_cli.retrieval.query_builders import queries_for_core_course


def test_queries_for_core_course_adds_degree_plan_queries_for_generic_title() -> None:
    program = {
        "identity": {
            "institution_name": "UC Berkeley",
            "program_name": "MIMS",
        }
    }
    qs = queries_for_core_course(
        program,
        "Core course 2",
        "mims_core_2",
        seed_url="https://www.ischool.berkeley.edu/programs/mims",
    )
    joined = " ".join(qs).lower()
    assert "degree requirements" in joined
    assert "core curriculum" in joined or "required core" in joined
