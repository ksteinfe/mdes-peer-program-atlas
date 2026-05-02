"""curriculum_units."""

from __future__ import annotations

from peer_atlas_cli.curriculum_units import recompute_normalized_unit_weights


def test_recompute_normalized_unit_weights() -> None:
    program = {
        "curriculum": {
            "core_courses": [
                {"units_or_credits": 4, "normalized_unit_weight": None},
                {"units_or_credits": 2, "normalized_unit_weight": None},
            ],
            "elective_courses": [
                {
                    "course_id": "Open Elective",
                    "units_or_credits": 2,
                    "normalized_unit_weight": None,
                },
            ],
        }
    }
    recompute_normalized_unit_weights(program)
    avg = (4 + 2 + 2) / 3
    assert abs(program["curriculum"]["core_courses"][0]["normalized_unit_weight"] - 4 / avg) < 1e-9
    assert abs(program["curriculum"]["elective_courses"][0]["normalized_unit_weight"] - 2 / avg) < 1e-9


def test_recompute_all_null_units() -> None:
    program = {
        "curriculum": {
            "core_courses": [{"units_or_credits": None, "normalized_unit_weight": 1}],
            "elective_courses": [],
        }
    }
    recompute_normalized_unit_weights(program)
    assert program["curriculum"]["core_courses"][0]["normalized_unit_weight"] is None
