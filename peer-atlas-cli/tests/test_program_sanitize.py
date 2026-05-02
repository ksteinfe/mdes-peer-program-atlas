"""program_sanitize helpers."""

from __future__ import annotations

from peer_atlas_cli.program_sanitize import normalize_derivation_notes, normalize_sources


def test_normalize_derivation_notes_coerces_strings() -> None:
    p = {
        "base_url": "https://example.edu/",
        "degree_cost": {
            "derivation_notes": [
                "First note as plain string.",
                {"derived_feature": "x", "source_id": "old", "note": "legacy"},
            ]
        },
    }
    n = normalize_derivation_notes(p, default_source_url="https://example.edu/")
    assert n == 2
    notes = p["degree_cost"]["derivation_notes"]
    assert notes[0]["note"] == "First note as plain string."
    assert notes[0]["source_url"] == "https://example.edu/"
    assert notes[1]["source_url"] == "old"


def test_normalize_sources_new_shape() -> None:
    p = {
        "positioning": {
            "sources": [
                {
                    "url": "https://example.edu/about-mdes",
                    "direct_text": "long excerpt",
                    "llm_summary": "About the program.",
                    "retrieved_date": "2026-05-02",
                    "notes": "n",
                }
            ]
        }
    }
    n = normalize_sources(p)
    assert n == 1
    s = p["positioning"]["sources"][0]
    assert set(s.keys()) == {"url", "llm_title", "llm_summary", "retrieved_date"}
    assert s["url"] == "https://example.edu/about-mdes"
    assert s["llm_summary"] == "About the program."
    assert s["retrieved_date"] == "2026-05-02"
    assert s["llm_title"] == "About mdes"
