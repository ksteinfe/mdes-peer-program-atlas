"""program_sanitize helpers."""

from __future__ import annotations

from peer_atlas_cli.program_sanitize import (
    coalesce_curriculum_subtree_from_llm,
    normalize_core_course_learning_outcomes,
    normalize_derivation_notes,
    normalize_sources,
)


def test_normalize_derivation_notes_coerces_strings() -> None:
    p = {
        "base_url": "https://example.edu/",
        "degree_cost": {
            "derivation_notes": [
                "First note as plain string.",
                {"derived_feature": "x", "source_id": "old", "note": "legacy"},
            ]
        },
    }
    n = normalize_derivation_notes(p, default_source_url="https://example.edu/")
    assert n == 2
    notes = p["degree_cost"]["derivation_notes"]
    assert notes[0]["note"] == "First note as plain string."
    assert notes[0]["source_url"] == "https://example.edu/"
    assert notes[1]["source_url"] == "old"


def test_normalize_sources_new_shape() -> None:
    p = {
        "positioning": {
            "sources": [
                {
                    "url": "https://example.edu/about-mdes",
                    "direct_text": "long excerpt",
                    "llm_summary": "About the program.",
                    "retrieved_date": "2026-05-02",
                    "notes": "n",
                }
            ]
        }
    }
    n = normalize_sources(p)
    assert n == 1
    s = p["positioning"]["sources"][0]
    assert set(s.keys()) == {"url", "llm_title", "llm_summary", "retrieved_date"}
    assert s["url"] == "https://example.edu/about-mdes"
    assert s["llm_summary"] == "About the program."
    assert s["retrieved_date"] == "2026-05-02"
    assert s["llm_title"] == "About mdes"


def test_normalize_core_course_learning_outcomes() -> None:
    p = {
        "curriculum": {
            "core_courses": [
                {},
                {"learning_outcomes": "not a list"},
                {"learning_outcomes": ["  a  ", "", "b"]},
            ]
        }
    }
    normalize_core_course_learning_outcomes(p)
    rows = p["curriculum"]["core_courses"]
    assert rows[0]["learning_outcomes"] == []
    assert rows[1]["learning_outcomes"] == []
    assert rows[2]["learning_outcomes"] == ["a", "b"]


def test_coalesce_curriculum_subtree_from_llm() -> None:
    cur = {
        "derived_features": {},
        "core_courses": [
            {
                "course_id": "x",
                "course_title": "Y",
                "course_type": "design_methods_systems",
                "sequence_position": 1,
                "course_summary": "s",
                "source_url": "https://example.edu/",
            }
        ],
        "elective_requirements": [
            {
                "requirement_name": "Elective",
                "requirement_description": "d",
                "primary_type": "open_or_other",
                "course_summary": "c",
                "source_url": "https://example.edu/",
            }
        ],
        "sources": [],
        "derivation_notes": [],
    }
    coalesce_curriculum_subtree_from_llm(cur)
    core = cur["core_courses"][0]
    assert "course_type" not in core
    assert core["primary_type"] == "design_methods_systems"
    assert core["units_or_credits"] is None
    assert core["normalized_unit_weight"] is None
    assert core["secondary_type"] is None
    assert core["learning_outcomes"] == []
    assert isinstance(cur["elective_requirements"], str)
    assert "Elective" in cur["elective_requirements"]
    ec = cur["elective_courses"]
    assert len(ec) == 1
    assert ec[0]["course_id"] == "Elective"
    assert ec[0]["units_or_credits"] is None
    assert ec[0]["normalized_unit_weight"] is None
