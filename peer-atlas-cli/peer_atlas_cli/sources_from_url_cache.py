"""Build program ``sources`` URL inventory from on-disk url-cache JSON entries."""

from __future__ import annotations

import json
import pathlib
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from peer_atlas_cli.retrieval.host_scope import registered_domain_for_url
from peer_atlas_cli.retrieval.url_cache import cache_dir_for_repo
from peer_atlas_cli.retrieval.url_normalize import normalize_url

_MIN_NEEDLE_LEN = 4


def _read_normalized_url_from_cache_file(path: pathlib.Path) -> str | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    u = data.get("url")
    if not isinstance(u, str) or not u.strip():
        return None
    n = normalize_url(u.strip())
    return n or None


def iter_cache_entry_urls(cache_dir: pathlib.Path) -> Iterator[str]:
    """Yield normalized ``url`` strings from each ``*.json`` file in ``cache_dir``."""
    if not cache_dir.is_dir():
        return
    for path in sorted(cache_dir.glob("*.json")):
        n = _read_normalized_url_from_cache_file(path)
        if n:
            yield n


def _cache_filename_match_needles(base_url: str) -> set[str]:
    """Substrings to match against cache filenames (lowercased)."""
    u = normalize_url((base_url or "").strip())
    needles: set[str] = set()
    if not u:
        return needles
    rd = registered_domain_for_url(u)
    if rd and len(rd) >= _MIN_NEEDLE_LEN:
        needles.add(rd.lower())
    try:
        host = (urlparse(u).hostname or "").lower()
    except ValueError:
        host = ""
    if host and len(host) >= _MIN_NEEDLE_LEN:
        needles.add(host)
        if host.startswith("www.") and len(host) > 4:
            needles.add(host[4:])
    return needles


def iter_urls_from_cache_files_matching_needles(
    cache_dir: pathlib.Path, needles: Iterable[str]
) -> Iterator[str]:
    """Yield URLs from cache JSON files whose filename contains any ``needle`` (lowercase)."""
    if not cache_dir.is_dir():
        return
    nlow = {n.lower() for n in needles if n and len(n) >= _MIN_NEEDLE_LEN}
    if not nlow:
        return
    for path in cache_dir.glob("*.json"):
        fn = path.name.lower()
        if not any(n in fn for n in nlow):
            continue
        n = _read_normalized_url_from_cache_file(path)
        if n:
            yield n


def index_urls_by_registered_domain(urls: Iterable[str]) -> dict[str, list[str]]:
    """
    Bucket normalized URLs by registrable domain (same rule as
    :func:`peer_atlas_cli.retrieval.host_scope.registered_domain_for_url`).
    """
    buckets: dict[str, set[str]] = defaultdict(set)
    for u in urls:
        rd = registered_domain_for_url(u)
        if not rd:
            continue
        buckets[rd].add(u)
    return {k: sorted(v) for k, v in buckets.items()}


def collect_sources_for_program(
    program: dict[str, Any],
    cache_dir: pathlib.Path,
    index: Mapping[str, Sequence[str]],
) -> list[str]:
    """
    All normalized URLs for ``program``: registrable-domain bucket for ``base_url``
    plus any cache file whose filename contains the program's registrable domain or
    hostname (so hosts like ``arch.columbia.edu`` still match ``columbia.edu`` files).
    """
    bu = normalize_url(str(program.get("base_url") or "").strip())
    anchor = registered_domain_for_url(bu) if bu else None
    acc: set[str] = set()
    if anchor:
        acc.update(index.get(anchor, ()))
    needles = _cache_filename_match_needles(str(program.get("base_url") or ""))
    acc.update(iter_urls_from_cache_files_matching_needles(cache_dir, needles))
    return sorted(acc)


def set_program_sources_from_index(
    program: dict[str, Any],
    index: Mapping[str, Sequence[str]],
) -> None:
    """Assign ``sources`` from the global domain index only (used in unit tests)."""
    bu = normalize_url(str(program.get("base_url") or "").strip())
    anchor = registered_domain_for_url(bu) if bu else None
    rows = list(index.get(anchor, ())) if anchor else []
    program["sources"] = sorted(set(rows))


def rebuild_all_program_sources(corpus: dict[str, Any], repo_root: pathlib.Path) -> None:
    """Mutate each program's ``sources`` from url-cache (domain index + filename match)."""
    cache_dir = cache_dir_for_repo(repo_root)
    index = index_urls_by_registered_domain(iter_cache_entry_urls(cache_dir))
    programs = corpus.get("programs")
    if not isinstance(programs, list):
        return
    for p in programs:
        if isinstance(p, dict):
            p["sources"] = collect_sources_for_program(p, cache_dir, index)
