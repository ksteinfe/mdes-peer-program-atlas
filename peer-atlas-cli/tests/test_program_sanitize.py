"""program_sanitize helpers."""

from __future__ import annotations

from peer_atlas_cli.program_sanitize import (
    coalesce_curriculum_subtree_from_llm,
    coerce_llm_rationale_object,
    hoist_nested_curriculum_llm_rationales,
    normalize_core_course_learning_outcomes,
    normalize_curriculum_electives,
    normalize_llm_rationales,
)
from peer_atlas_cli.publish_coerce import coerce_none_strings_for_publish


def test_normalize_llm_rationales_coerces_strings() -> None:
    p: dict = {
        "llm_rationales": [
            "bare string note",
            {"feature": "x", "source_url": "https://a.edu/", "note": "ok"},
        ]
    }
    n = normalize_llm_rationales(p, default_source_url="https://example.edu/")
    assert n == 1
    notes = p["llm_rationales"]
    assert notes[0]["note"] == "bare string note"
    assert notes[0]["llm_title"] != ""
    assert notes[0]["retrieved_date"] == ""
    assert notes[1]["note"] == "ok"
    assert set(notes[1].keys()) == {
        "feature",
        "source_url",
        "note",
        "llm_title",
        "retrieved_date",
    }


def test_coerce_llm_rationale_object_five_keys() -> None:
    raw = {
        "feature": "curriculum.core_courses",
        "source_url": "https://www.ischool.berkeley.edu/programs/mims/degreerequirements",
        "note": "No named courses in snippet.",
        "llm_title": "",
        "retrieved_date": "",
    }
    out = coerce_llm_rationale_object(raw, default_source_url="https://seed.edu/")
    assert out["feature"] == "curriculum.core_courses"
    assert (
        out["source_url"]
        == "https://www.ischool.berkeley.edu/programs/mims/degreerequirements"
    )
    assert out["note"] == "No named courses in snippet."
    assert out["llm_title"] == "Degreerequirements"
    assert out["retrieved_date"] == ""
    assert set(out.keys()) == {
        "feature",
        "source_url",
        "note",
        "llm_title",
        "retrieved_date",
    }


def test_normalize_llm_rationales_drops_unknown_keys_from_output_shape() -> None:
    p: dict = {
        "llm_rationales": [
            {
                "feature": "a",
                "source_url": "https://x.edu/",
                "note": "n",
                "llm_title": "T",
                "retrieved_date": "2026-01-01",
                "rationale": "ignored",
            }
        ]
    }
    n = normalize_llm_rationales(p, default_source_url="https://example.edu/")
    assert n == 1
    row = p["llm_rationales"][0]
    assert row["note"] == "n"
    assert set(row.keys()) == {
        "feature",
        "source_url",
        "note",
        "llm_title",
        "retrieved_date",
    }


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
        "electives": {"summary": "Elective prose.", "estimated_elective_course_count": 10},
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
    assert cur["electives"]["summary"] == "Elective prose."
    assert cur["electives"]["estimated_elective_course_count"] == 10
    assert "derived_features" not in cur


def test_normalize_curriculum_electives_blank_estimated_count_becomes_null() -> None:
    cur = {
        "electives": {
            "summary": "  prose  ",
            "estimated_elective_course_count": "",
        }
    }
    normalize_curriculum_electives(cur)
    assert cur["electives"]["estimated_elective_course_count"] is None
    assert cur["electives"]["summary"] == "prose"


def test_normalize_curriculum_electives_numeric_string_count() -> None:
    cur = {"electives": {"summary": "", "estimated_elective_course_count": " 12 "}}
    normalize_curriculum_electives(cur)
    assert cur["electives"]["estimated_elective_course_count"] == 12


def test_coerce_none_strings_preserves_null_elective_count() -> None:
    program = {
        "curriculum": {
            "electives": {
                "summary": "x",
                "estimated_elective_course_count": None,
            }
        }
    }
    coerce_none_strings_for_publish(program)
    assert program["curriculum"]["electives"]["estimated_elective_course_count"] is None


def test_hoist_nested_curriculum_llm_rationales() -> None:
    p: dict = {
        "base_url": "https://example.edu/",
        "llm_rationales": [
            {
                "feature": "program.citation",
                "source_url": "https://example.edu/a",
                "note": "",
                "llm_title": "A",
                "retrieved_date": "",
            }
        ],
        "curriculum": {
            "llm_rationales": [
                {
                    "feature": "curriculum.electives",
                    "source_url": "https://example.edu/other",
                    "note": "Elective count uncertain.",
                    "llm_title": "Other",
                    "retrieved_date": "",
                }
            ],
        },
    }
    hoist_nested_curriculum_llm_rationales(p)
    assert "llm_rationales" not in p["curriculum"]
    assert len(p["llm_rationales"]) == 2
    assert p["llm_rationales"][1]["feature"] == "curriculum.electives"
