"""research.fetch helpers."""

from __future__ import annotations

from peer_atlas_cli import research


def test_headers_chrome_like_and_referer() -> None:
    h = research._headers_for_url("https://design.berkeley.edu/programs")
    assert "Chrome" in h["User-Agent"]
    assert h["Referer"] == "https://design.berkeley.edu/"
    assert h["Sec-Fetch-Site"] == "same-origin"


def test_headers_cookie_from_env(monkeypatch) -> None:
    monkeypatch.setenv("PEER_ATLAS_FETCH_COOKIE", "session=abc")
    h = research._headers_for_url("https://example.com/")
    assert h["Cookie"] == "session=abc"
