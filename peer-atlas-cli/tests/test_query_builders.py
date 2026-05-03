"""query_builders."""

from __future__ import annotations

from peer_atlas_cli.categories import load_tavily_search_guidance
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.retrieval.query_builders import (
    queries_for_core_course,
    queries_for_node,
)


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
    assert "required course" in joined or "core curriculum" in joined or "required core" in joined


def test_curriculum_overview_returns_two_queries() -> None:
    program = {
        "identity": {"institution_name": "Ex U", "program_name": "MDes"},
    }
    qs = queries_for_node(
        "curriculum_overview",
        program,
        seed_url="https://ex.edu/p",
        user_query="",
        repo_root=find_repo_root(),
    )
    assert len(qs) == 2
    assert qs[0] != qs[1]
    assert "elective" in qs[1].lower()


def test_official_program_label_used_for_queries() -> None:
    program = {
        "atlas_search_context": {
            "official_program_label": "Custom Official Program Name",
        },
        "identity": {"institution_name": "Wrong Host", "program_name": "Wrong Path"},
    }
    qs = queries_for_node(
        "positioning",
        program,
        seed_url="https://ex.edu/",
        user_query="ignored when label set",
        repo_root=find_repo_root(),
    )
    assert len(qs) == 1
    assert qs[0].startswith("Custom Official Program Name")


def test_degree_cost_uses_resolved_label_like_duration() -> None:
    program = {
        "identity": {"institution_name": "State U", "program_name": "MFA"},
    }
    qs = queries_for_node(
        "degree_cost",
        program,
        seed_url="https://ex.edu/",
        user_query="",
        repo_root=find_repo_root(),
    )
    assert len(qs) == 1
    assert qs[0] == "State U MFA tuition fees cost"


def test_degree_cost_uses_official_program_label_over_institution() -> None:
    program = {
        "atlas_search_context": {
            "official_program_label": "UC Berkeley Master of Information Management and Systems",
        },
        "identity": {
            "institution_name": "ischool.berkeley.edu",
            "program_name": "Mims",
        },
    }
    qs = queries_for_node(
        "degree_cost",
        program,
        seed_url="https://www.ischool.berkeley.edu/programs/mims",
        user_query="",
        repo_root=find_repo_root(),
    )
    assert len(qs) == 1
    assert qs[0].startswith("UC Berkeley Master of Information Management and Systems")
    assert "tuition fees cost" in qs[0].lower()


def test_degree_cost_when_only_program_name() -> None:
    program = {
        "identity": {"institution_name": "", "program_name": "Only Program"},
    }
    qs = queries_for_node(
        "degree_cost",
        program,
        seed_url="https://ex.edu/",
        user_query="",
        repo_root=find_repo_root(),
    )
    assert len(qs) == 1
    assert qs[0] == "Only Program tuition fees cost"


def test_load_tavily_search_guidance_returns_dict() -> None:
    root = find_repo_root()
    g = load_tavily_search_guidance(root)
    assert isinstance(g, dict)
    assert g.get("schema_version") == 1
    assert "nodes" in g
