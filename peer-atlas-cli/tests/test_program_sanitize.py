"""program_sanitize helpers."""

from __future__ import annotations

from peer_atlas_cli.program_sanitize import (
    coalesce_curriculum_subtree_from_llm,
    coerce_llm_rationale_object,
    normalize_core_course_learning_outcomes,
    normalize_derivation_notes,
    normalize_sources,
)


def test_normalize_llm_rationales_coerces_strings() -> None:
    p: dict = {
        "llm_rationales": [
            "bare string note",
            {"feature": "x", "source_url": "https://a.edu/", "note": "ok"},
        ]
    }
    n = normalize_derivation_notes(p, default_source_url="https://example.edu/")
    assert n == 1
    notes = p["llm_rationales"]
    assert notes[0]["note"] == "bare string note"
    assert notes[1]["note"] == "ok"


def test_coerce_llm_rationale_object_maps_rationale_to_note() -> None:
    raw = {
        "feature": "curriculum.core_courses",
        "source_url": "https://www.ischool.berkeley.edu/programs/mims/degreerequirements",
        "rationale": "No named courses in snippet.",
    }
    out = coerce_llm_rationale_object(raw, default_source_url="https://seed.edu/")
    assert out == {
        "feature": "curriculum.core_courses",
        "source_url": "https://www.ischool.berkeley.edu/programs/mims/degreerequirements",
        "note": "No named courses in snippet.",
    }
    assert set(out.keys()) == {"feature", "source_url", "note"}


def test_normalize_llm_rationales_strips_rationale_key() -> None:
    p: dict = {
        "llm_rationales": [
            {
                "feature": "a",
                "source_url": "https://x.edu/",
                "rationale": "wrong key",
            }
        ]
    }
    n = normalize_derivation_notes(p, default_source_url="https://example.edu/")
    assert n == 1
    row = p["llm_rationales"][0]
    assert row == {"feature": "a", "source_url": "https://x.edu/", "note": "wrong key"}


def test_normalize_sources_new_shape() -> None:
    p: dict = {
        "sources": [
            {
                "url": "https://example.edu/foo",
                "llm_title": "",
                "llm_summary": None,
                "retrieved_date": None,
                "source_id": "legacy",
            }
        ]
    }
    n = normalize_sources(p)
    assert n == 1
    s = p["sources"][0]
    assert s["url"] == "https://example.edu/foo"
    assert s["llm_title"]
    assert "source_id" not in s


def test_normalize_core_course_learning_outcomes() -> None:
    p = {
        "curriculum": {
            "core_courses": [
                {},
                {"learning_outcomes": None},
                {"learning_outcomes": "not a list"},
                {"learning_outcomes": ["  a  ", "", "b"]},
            ]
        }
    }
    normalize_core_course_learning_outcomes(p)
    rows = p["curriculum"]["core_courses"]
    assert rows[0]["learning_outcomes"] == []
    assert rows[1]["learning_outcomes"] == []
    assert rows[2]["learning_outcomes"] == []
    assert rows[3]["learning_outcomes"] == ["a", "b"]


def test_coalesce_curriculum_subtree_from_llm() -> None:
    cur = {
        "unit_system": "semester_credit_hours",
        "sequencedness": "flexible",
        "curriculum_summary": "",
        "offers_specialization": True,
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
    }
    coalesce_curriculum_subtree_from_llm(cur)
    assert cur["offers_specialization"] is True
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
