"""json_paths helpers."""

from __future__ import annotations

from peer_atlas_cli.json_paths import get_path, parse_json_path, path_exists, set_path


def test_parse_json_path() -> None:
    assert parse_json_path("a.b[2].c") == ["a", "b", 2, "c"]
    assert parse_json_path("curriculum.core_courses.0.course_summary") == [
        "curriculum",
        "core_courses",
        0,
        "course_summary",
    ]


def test_get_set_path() -> None:
    obj = {"x": [{"y": 1}]}
    assert get_path(obj, "x[0].y") == 1
    set_path(obj, "x[0].y", 9)
    assert obj["x"][0]["y"] == 9


def test_set_path_dot_numeric_list_index() -> None:
    obj: dict = {"curriculum": {"core_courses": [{"course_summary": "a"}]}}
    set_path(obj, "curriculum.core_courses.0.course_summary", "patched")
    assert obj["curriculum"]["core_courses"][0]["course_summary"] == "patched"


def test_path_exists() -> None:
    assert path_exists({"a": {"b": 1}}, "a.b")
    assert not path_exists({"a": {}}, "a.b")
