"""reconsider_evidence helpers."""

from __future__ import annotations

from peer_atlas_cli.reconsider_evidence import build_reconsider_evidence, rationales_for_node


def test_rationales_for_node_curriculum_prefix() -> None:
    p = {
        "llm_rationales": [
            {"feature": "positioning.positioning_tags", "source_url": "https://a", "note": "x"},
            {"feature": "curriculum.unit_system", "source_url": "https://b", "note": "y"},
            {"feature": "curriculum.core_courses.0.primary_type", "source_url": "", "note": "z"},
        ]
    }
    cur = rationales_for_node("curriculum", p)
    assert len(cur) == 2
    assert cur[0]["feature"] == "curriculum.unit_system"


def test_rationales_curriculum_overview_matches_curriculum_paths() -> None:
    p = {
        "llm_rationales": [
            {"feature": "duration.duration_category", "source_url": "", "note": "d"},
            {"feature": "curriculum.sequencedness", "source_url": "https://c", "note": "s"},
        ]
    }
    ov = rationales_for_node("curriculum_overview", p)
    assert len(ov) == 1
    assert ov[0]["feature"] == "curriculum.sequencedness"


def test_rationales_exact_node_feature() -> None:
    p = {"llm_rationales": [{"feature": "identity", "source_url": "", "note": "n"}]}
    assert len(rationales_for_node("identity", p)) == 1


def test_build_reconsider_evidence_asks_for_appended_rationales() -> None:
    s = build_reconsider_evidence(
        user_instruction="x",
        rationales=[],
        fetched_pages="(none)\n",
        primary_response_key="positioning",
    )
    assert "appended" in s.lower()
    assert "llm_rationales" in s
    assert "positioning" in s
