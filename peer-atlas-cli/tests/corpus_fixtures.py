"""Minimal corpus rows for tests (do not depend on corpus/programs.json contents)."""

from __future__ import annotations

from typing import Any


def minimal_valid_program(*, program_id: str = "fixture_program") -> dict[str, Any]:
    """One program that passes validate_corpus when not in draft mode."""
    return {
        "program_id": program_id,
        "base_url": "https://fixture.example.edu/program",
        "sources": [
            {
                "url": "https://fixture.example.edu/program",
                "llm_title": "Program",
                "llm_summary": "",
                "retrieved_date": "",
            }
        ],
        "llm_rationales": [],
        "identity": {
            "institution_name": "Fixture University",
            "program_name": "Fixture MDes",
            "credential_name": "MDes",
            "degree_type": "MDes",
            "host_academic_units": ["Design"],
            "host_academic_model": "design_hosted",
            "location_label": "United States",
        },
        "positioning": {
            "positioning_summary": "",
            "positioning_tags": ["professional"],
        },
        "duration": {
            "length_in_berkeley_semesters": None,
            "duration_category": "variable_or_custom",
        },
        "degree_cost": {
            "base_currency": "",
            "exchange_rate_to_usd": None,
            "comparison_cost_usd": None,
            "total_degree_cost_base_currency": None,
        },
        "curriculum": {
            "unit_system": "semester_credit_hours",
            "sequencedness": "flexible",
            "curriculum_summary": "",
            "offers_specialization": False,
            "evidence_curriculum_summary": "",
            "core_courses": [
                {
                    "course_id": "FIXTURE 100",
                    "course_title": "Fixture studio",
                    "units_or_credits": 4,
                    "normalized_unit_weight": 1.2,
                    "sequence_position": 1,
                    "primary_type": "design_studio",
                    "secondary_type": None,
                    "course_summary": "Fixture course.",
                    "source_url": "https://fixture.example.edu/course",
                    "learning_outcomes": [],
                }
            ],
            "elective_requirements": "",
            "elective_courses": [],
        },
        "verification": {
            "status": "llm_extracted",
            "verified_by": "",
            "verified_date": "",
        },
    }


def minimal_valid_corpus(*, program_id: str = "fixture_program") -> dict[str, Any]:
    return {
        "corpus_metadata": {
            "version": 1,
            "description": "MDes Peer Program Comparator Corpus",
        },
        "programs": [minimal_valid_program(program_id=program_id)],
    }
