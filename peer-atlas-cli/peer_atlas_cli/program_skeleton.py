"""Draft program skeleton for multi-step ingest."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Keep in lockstep with `schemas/program_draft.schema.json` → `properties.atlas_ingest.properties.stage.enum`.
# Any new `set_ingest_stage(..., "…")` value must be added here and in that enum (CI checks via test).
ATLAS_INGEST_STAGES: frozenset[str] = frozenset(
    {
        "skeleton",
        "positioning",
        "duration",
        "degree_cost",
        "curriculum",
        "curriculum_digest",
        "curriculum_overview",
        "curriculum_courses",
        "curriculum_course_research",
        "curriculum_course_llm",
        "identity",
        "complete",
    }
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_ingest_skeleton(program_id: str, base_url: str) -> dict[str, Any]:
    """Minimal valid object under program_draft.schema.json (ingest)."""
    return {
        "program_id": program_id,
        "base_url": (base_url or "").strip(),
        "atlas_ingest": {"stage": "skeleton", "updated_at": _iso_now()},
        "sources": [],
        "llm_rationales": [],
        "identity": {
            "institution_name": None,
            "program_name": None,
            "credential_name": None,
            "degree_type": None,
            "host_academic_units": [],
            "host_academic_model": None,
            "location_label": None,
        },
        "positioning": {
            "positioning_summary": None,
            "positioning_tags": [],
        },
        "duration": {
            "length_in_berkeley_semesters": None,
            "duration_category": None,
        },
        "degree_cost": {
            "base_currency": None,
            "exchange_rate_to_usd": None,
            "comparison_cost_usd": None,
            "total_degree_cost_base_currency": None,
        },
        "curriculum": {
            "unit_system": None,
            "sequencedness": None,
            "curriculum_summary": None,
            "offers_specialization": None,
            "evidence_curriculum_summary": None,
            "core_courses": [],
            "elective_requirements": "",
            "elective_courses": [],
        },
        "verification": {
            "status": "llm_extracted",
            "verified_by": "",
            "verified_date": "",
        },
    }


def set_ingest_stage(program: dict[str, Any], stage: str) -> None:
    if stage not in ATLAS_INGEST_STAGES:
        raise ValueError(
            f"atlas_ingest.stage {stage!r} is not allowed. "
            "Add it to ATLAS_INGEST_STAGES in program_skeleton.py and to "
            "schemas/program_draft.schema.json (atlas_ingest.properties.stage.enum)."
        )
    program["atlas_ingest"] = {"stage": stage, "updated_at": _iso_now()}


def strip_atlas_ingest(program: dict[str, Any]) -> None:
    program.pop("atlas_ingest", None)
