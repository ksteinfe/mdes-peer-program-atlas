"""program_dates helpers."""

from __future__ import annotations

from peer_atlas_cli.program_dates import index_most_recently_added_program


def test_index_most_recently_added_by_date() -> None:
    programs = [
        {"program_id": "a", "date_added": "2026-01-01T00:00:00Z"},
        {"program_id": "b", "date_added": "2026-06-01T00:00:00Z"},
        {"program_id": "c", "date_added": "2026-03-01T00:00:00Z"},
    ]
    assert index_most_recently_added_program(programs) == 1


def test_index_most_recently_added_tie_breaks_to_larger_index() -> None:
    programs = [
        {"program_id": "a", "date_added": "2026-01-01T00:00:00Z"},
        {"program_id": "b", "date_added": "2026-01-01T00:00:00Z"},
    ]
    assert index_most_recently_added_program(programs) == 1


def test_index_most_recently_added_fallback_last_when_no_dates() -> None:
    programs = [{"program_id": "x"}, {"program_id": "y"}]
    assert index_most_recently_added_program(programs) == 1


def test_index_most_recently_added_empty() -> None:
    assert index_most_recently_added_program([]) is None
