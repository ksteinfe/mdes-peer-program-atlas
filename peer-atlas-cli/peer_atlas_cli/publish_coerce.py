"""Coerce JSON null to \"\" for strict program.schema string fields before publish."""

from __future__ import annotations

from typing import Any

# Keys whose JSON null is valid in the published program schema
_STRICT_NULLABLE_KEYS: frozenset[str] = frozenset(
    {
        "units_or_credits",
        "normalized_unit_weight",
        "sequence_position",
        "length_in_berkeley_semesters",
        "exchange_rate_to_usd",
        "comparison_cost_usd",
        "total_degree_cost_base_currency_single",
        "total_degree_cost_base_currency_domestic_or_resident",
        "total_degree_cost_base_currency_international_or_nonresident",
        "total_units_or_credits",
        "has_required_core",
        "has_structured_electives",
        "has_open_electives",
        "has_required_studio_sequence",
        "has_required_thesis_or_capstone",
        "has_internship_or_professional_practice_requirement",
        "secondary_type",
    }
)


def coerce_none_strings_for_publish(program: dict[str, Any]) -> None:
    """In-place: replace None with \"\" except for known nullable fields."""

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if v is None and k not in _STRICT_NULLABLE_KEYS:
                    obj[k] = ""
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(obj, list):
            for it in obj:
                if isinstance(it, (dict, list)):
                    walk(it)

    walk(program)
