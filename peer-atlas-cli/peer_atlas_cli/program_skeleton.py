"""Draft program skeleton for multi-step ingest."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_ingest_skeleton(program_id: str, base_url: str) -> dict[str, Any]:
    """Minimal valid object under program_draft.schema.json (ingest)."""
    return {
        "program_id": program_id,
        "base_url": (base_url or "").strip(),
        "atlas_ingest": {"stage": "skeleton", "updated_at": _iso_now()},
        "identity": {
            "institution_name": None,
            "program_name": None,
            "credential_name": None,
            "degree_type": None,
            "host_academic_units": [],
            "host_academic_model": None,
            "location": {"country": None, "state_or_region": None},
            "sources": [],
        },
        "positioning": {
            "derived_features": {
                "positioning_summary": None,
                "positioning_tags": [],
            },
            "sources": [],
            "derivation_notes": [],
        },
        "duration": {
            "derived_features": {
                "length_in_berkeley_semesters": None,
                "duration_category": None,
            },
            "sources": [],
            "derivation_notes": [],
        },
        "degree_cost": {
            "derived_features": {
                "base_currency": None,
                "exchange_rate_to_usd": None,
                "exchange_rate_date": None,
                "comparison_cost_usd": None,
                "total_degree_cost_base_currency_single": None,
                "total_degree_cost_base_currency_domestic_or_resident": None,
                "total_degree_cost_base_currency_international_or_nonresident": None,
                "comparison_cost_method": None,
                "cost_basis": None,
            },
            "sources": [],
            "derivation_notes": [],
        },
        "curriculum": {
            "derived_features": {
                "has_required_core": None,
                "has_structured_electives": None,
                "has_open_electives": None,
                "has_required_studio_sequence": None,
                "has_required_thesis_or_capstone": None,
                "has_internship_or_professional_practice_requirement": None,
                "total_units_or_credits": None,
                "unit_system": None,
                "sequencedness": None,
                "curriculum_summary": None,
            },
            "core_courses": [],
            "elective_requirements": [],
            "sources": [],
            "derivation_notes": [],
        },
        "verification": {
            "status": "llm_extracted",
            "verified_by": None,
            "verified_date": None,
            "verification_scope": [],
            "verification_notes": None,
            "fields_needing_review": [],
        },
    }


def set_ingest_stage(program: dict[str, Any], stage: str) -> None:
    program["atlas_ingest"] = {"stage": stage, "updated_at": _iso_now()}


def strip_atlas_ingest(program: dict[str, Any]) -> None:
    program.pop("atlas_ingest", None)
