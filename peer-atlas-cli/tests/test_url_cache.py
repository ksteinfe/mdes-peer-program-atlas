"""URL cache and normalization."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from peer_atlas_cli.retrieval.url_cache import (
    read_cached_body,
    write_cached_body,
)
from peer_atlas_cli.retrieval.url_normalize import cache_filename_for_url, cache_key_for_url, normalize_url


def test_normalize_url_strips_fragment_and_default_port() -> None:
    assert normalize_url("HTTPS://Example.COM:443/foo?b=2&a=1#x") == "https://example.com/foo?a=1&b=2"


def test_cache_key_stable() -> None:
    a = cache_key_for_url("https://example.com/a")
    b = cache_key_for_url("https://example.com/a#frag")
    assert a == b
    assert len(a) == 64


def test_cache_filename_human_readable() -> None:
    fn = cache_filename_for_url("https://design.berkeley.edu/programs/mdes")
    assert fn.endswith(".json")
    assert "design.berkeley.edu" in fn


def test_cache_ttl_expiry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEER_ATLAS_FETCH_CACHE_TTL_SECONDS", "1")
    url = "https://example.com/page"
    write_cached_body(tmp_path, url, "hello", http_status=200, notes="ok")
    assert read_cached_body(tmp_path, url) == "hello"
    p = tmp_path / cache_filename_for_url(url)
    data = json.loads(p.read_text(encoding="utf-8"))
    data["fetched_at"] = time.time() - 10.0
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert read_cached_body(tmp_path, url) is None
