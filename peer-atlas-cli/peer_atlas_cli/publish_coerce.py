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
        "cost_base_currency",
        "estimated_elective_course_count",
        "source_url",
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
