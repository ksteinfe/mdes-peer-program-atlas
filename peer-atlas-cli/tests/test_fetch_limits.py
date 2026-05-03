"""fetch_limits coalescing."""

from __future__ import annotations

import pytest

from peer_atlas_cli import fetch_limits as fl


def test_coalesce_zero_uses_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEER_ATLAS_FETCH_MAX_CHARS", "5000000")
    assert fl.coalesce_per_url_limit(0) == 5_000_000


def test_coalesce_small_request_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PEER_ATLAS_FETCH_MAX_CHARS", raising=False)
    assert fl.coalesce_per_url_limit(12_000) == 12_000


def test_coalesce_large_request_gets_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PEER_ATLAS_FETCH_MAX_CHARS", raising=False)
    monkeypatch.setenv("PEER_ATLAS_FETCH_EVIDENCE_FLOOR_CHARS", "9000000")
    assert fl.coalesce_per_url_limit(120_000) == 9_000_000


def test_raw_download_cap_at_least_coalesced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PEER_ATLAS_FETCH_MAX_CHARS", raising=False)
    c = fl.coalesce_per_url_limit(120_000)
    r = fl.raw_download_cap(120_000)
    assert r >= c
    assert r <= fl.fetch_char_ceiling()
