"""identity_fallback helpers."""

from __future__ import annotations

from peer_atlas_cli.identity_fallback import apply_identity_fallbacks


def test_fallback_from_url_only() -> None:
    p: dict = {"identity": {}}
    assert apply_identity_fallbacks(p, url="https://design.berkeley.edu/", query="") is True
    assert p["identity"]["institution_name"] == "design.berkeley.edu"
    assert p["identity"]["program_name"] == "Program (from URL)"


def test_fallback_from_url_path() -> None:
    p: dict = {"identity": {}}
    apply_identity_fallbacks(p, url="https://example.edu/mdes/overview", query="")
    assert p["identity"]["institution_name"] == "example.edu"
    assert "overview" in p["identity"]["program_name"].lower()


def test_fallback_query_program_name() -> None:
    p: dict = {"identity": {}}
    apply_identity_fallbacks(p, url="", query="CMU Master of Design")
    assert p["identity"]["program_name"] == "CMU Master of Design"
    assert "Unknown" in p["identity"]["institution_name"]
