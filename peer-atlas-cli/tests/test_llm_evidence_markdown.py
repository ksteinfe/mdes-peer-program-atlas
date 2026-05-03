"""Tests for HTML→main-content Markdown LLM path and JSON-safe storage."""

from __future__ import annotations

import json
import pathlib

import pytest

from peer_atlas_cli.retrieval.fetch_cached import fetch_url_text_cached
from peer_atlas_cli.retrieval.llm_evidence_markdown import sanitize_llm_text_for_json_storage
from peer_atlas_cli.retrieval.url_cache import (
    clear_cache_entry_for_url,
    read_raw_cache_entry,
    write_cached_body,
)


class _FakeLLM:
    def __init__(self, out: str = "# Title\n\nParagraph.") -> None:
        self.out = out
        self.calls = 0

    def complete(self, system: str, user: str, transcript_step: str = "") -> str:
        self.calls += 1
        return self.out


def test_sanitize_llm_text_for_json_storage_controls_and_surrogate() -> None:
    t = "a\x00b\nc" + "\ud800" + "d"
    out = sanitize_llm_text_for_json_storage(t)
    assert "\x00" not in out
    assert "\n" in out
    assert "\ufffd" in out
    json.dumps({"body_markdown": out}, ensure_ascii=False)


def test_write_cached_body_stores_sanitized_markdown(tmp_path: pathlib.Path) -> None:
    md = "intro\x01tail"
    write_cached_body(
        tmp_path,
        "https://example.com/a",
        "<p>body</p>",
        http_status=200,
        body_markdown=md,
    )
    raw = read_raw_cache_entry(tmp_path, "https://example.com/a")
    assert raw is not None
    stored = raw.get("body_markdown")
    assert isinstance(stored, str)
    assert "\x01" not in stored
    assert raw.get("body_chars") == len("<p>body</p>")
    assert raw.get("body_markdown_chars") == len(stored)
    json.loads(json.dumps(raw, ensure_ascii=False))


def test_fetch_cache_hit_backfills_body_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("PEER_ATLAS_FETCH_CACHE_DIR", str(tmp_path))
    url = "https://example.com/doc"
    write_cached_body(tmp_path, url, "<html> simplified </html>", http_status=200)
    fake = _FakeLLM("# From LLM\n\ncontent")
    text = fetch_url_text_cached(url, repo_root=tmp_path, llm_client=fake)
    assert text.startswith("# From LLM")
    assert fake.calls == 1
    raw = read_raw_cache_entry(tmp_path, url)
    assert raw is not None
    assert raw.get("body_markdown") == "# From LLM\n\ncontent"


def test_clear_cache_entry_for_url_removes_primary(tmp_path: pathlib.Path) -> None:
    url = "https://example.com/z"
    write_cached_body(tmp_path, url, "<p>x</p>", http_status=200)
    assert read_raw_cache_entry(tmp_path, url) is not None
    assert clear_cache_entry_for_url(tmp_path, url) == 1
    assert read_raw_cache_entry(tmp_path, url) is None

