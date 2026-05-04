"""sources_from_url_cache inventory."""

from __future__ import annotations

import json
from pathlib import Path

from peer_atlas_cli.sources_from_url_cache import (
    collect_sources_for_program,
    index_urls_by_registered_domain,
    iter_cache_entry_urls,
    rebuild_all_program_sources,
    set_program_sources_from_index,
)


def test_iter_cache_entry_urls_reads_url_key(tmp_path: Path) -> None:
    d = tmp_path / "url-cache"
    d.mkdir()
    (d / "a.json").write_text(
        json.dumps({"url": "https://WWW.Example.edu/path?x=1#f", "body": "x"}),
        encoding="utf-8",
    )
    (d / "bad.json").write_text("not json", encoding="utf-8")
    (d / "no_url.json").write_text(json.dumps({"body": "y"}), encoding="utf-8")
    assert list(iter_cache_entry_urls(d)) == ["https://www.example.edu/path?x=1"]


def test_index_and_assign_by_registered_domain(tmp_path: Path) -> None:
    d = tmp_path / "url-cache"
    d.mkdir()
    urls = [
        "https://a.berkeley.edu/one",
        "https://www.ischool.berkeley.edu/two",
        "https://example.com/other",
    ]
    for i, u in enumerate(urls):
        (d / f"f{i}.json").write_text(
            json.dumps({"url": u, "body": ""}), encoding="utf-8"
        )
    index = index_urls_by_registered_domain(iter_cache_entry_urls(d))
    assert "berkeley.edu" in index
    assert set(index["berkeley.edu"]) == {
        "https://a.berkeley.edu/one",
        "https://www.ischool.berkeley.edu/two",
    }
    p = {"base_url": "https://design.berkeley.edu/mdes", "sources": []}
    set_program_sources_from_index(p, index)
    assert p["sources"] == sorted(index["berkeley.edu"])
    p2 = {"base_url": "https://example.com/", "sources": []}
    set_program_sources_from_index(p2, index)
    assert p2["sources"] == ["https://example.com/other"]


def test_filename_needle_collects_url_when_index_bucket_differs(tmp_path: Path) -> None:
    """Cache filename contains arch.columbia.edu but JSON url host is unrelated."""
    cache = tmp_path / "url-cache"
    cache.mkdir(parents=True)
    fname = "www.arch.columbia.edu_programs_15-ms__a1b2c3d4e5.json"
    (cache / fname).write_text(
        json.dumps({"url": "https://cdn.example.net/mirror", "body": ""}),
        encoding="utf-8",
    )
    index = index_urls_by_registered_domain(iter_cache_entry_urls(cache))
    assert "columbia.edu" not in index
    prog = {
        "base_url": "https://www.arch.columbia.edu/programs/15-ms",
        "sources": [],
    }
    out = collect_sources_for_program(prog, cache, index)
    assert out == ["https://cdn.example.net/mirror"]


def test_rebuild_all_program_sources(tmp_path: Path) -> None:
    cache = tmp_path / ".peer-atlas" / "url-cache"
    cache.mkdir(parents=True)
    (cache / "x.json").write_text(
        json.dumps({"url": "https://sub.example.org/p", "body": ""}),
        encoding="utf-8",
    )
    corpus = {
        "corpus_metadata": {"version": 1},
        "programs": [
            {"base_url": "https://www.example.org/prog", "sources": ["stale"]},
            {"base_url": "https://other.edu/", "sources": []},
        ],
    }
    rebuild_all_program_sources(corpus, tmp_path)
    assert corpus["programs"][0]["sources"] == ["https://sub.example.org/p"]
    assert corpus["programs"][1]["sources"] == []
