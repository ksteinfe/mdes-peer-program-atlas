"""HTTP fetch with optional disk cache."""

from __future__ import annotations

import pathlib
from collections.abc import Callable

from peer_atlas_cli.fetch_limits import coalesce_per_url_limit, raw_download_cap
from peer_atlas_cli.html_text import html_to_visible_text
from peer_atlas_cli.research import fetch_url_text_lenient
from peer_atlas_cli.retrieval.url_cache import (
    cache_dir_for_repo,
    read_cached_entry,
    write_cached_body,
)


def _normalize_cached_body(text: str, *, max_chars: int) -> str:
    """Simplify HTML (head excerpt + main/article/body fields), then cap length."""
    plain = html_to_visible_text(text)
    lim = coalesce_per_url_limit(max_chars)
    if len(plain) > lim:
        return plain[:lim] + "\n\n[truncated]"
    return plain


def fetch_url_text_cached(
    url: str,
    *,
    repo_root: pathlib.Path,
    timeout: float = 30.0,
    max_chars: int = 120_000,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
) -> str:
    """Return page text (or placeholder on HTTP errors), using URL cache with TTL.

    If ``report`` is set, it is called with a short message when the response is
    not HTTP 200 (including when serving a non-200 result from an unexpired cache).

    If ``trace`` is set, it is called once per URL with ``fetch: cache <url>`` or
    ``fetch: network <url>`` so the CLI can show whether the body came from disk
    or a live request.

    Per-URL fetch limits are **coalesced** (see ``peer_atlas_cli.fetch_limits``): requests of **50_000+** characters are raised to a multi‑MiB **floor** (default ~8 MiB) and capped by **``PEER_ATLAS_FETCH_MAX_CHARS``** (default ~32 MiB) so curriculum-scale pages are not truncated at ~120 KiB unless you set a lower ceiling. Small limits (e.g. rationale fetches under 50k) stay exact.
    """
    cache_dir = cache_dir_for_repo(repo_root)
    entry = read_cached_entry(cache_dir, url)
    if entry is not None:
        if trace is not None:
            trace(f"fetch: cache {url}")
        body = entry.get("body")
        text = body if isinstance(body, str) else ""
        if report is not None:
            st = entry.get("http_status")
            if isinstance(st, int) and st != 200:
                notes = entry.get("notes")
                note_s = notes if isinstance(notes, str) else ""
                msg = f"URL fetch failed (cached HTTP {st}): {url}"
                if note_s.strip():
                    msg = f"{msg}\n  {note_s}"
                report(msg)
        return _normalize_cached_body(text, max_chars=max_chars)
    if trace is not None:
        trace(f"fetch: network {url}")
    raw_cap = raw_download_cap(max_chars)
    res = fetch_url_text_lenient(url, timeout=timeout, max_chars=raw_cap)
    if report is not None and res.status_code != 200:
        sc = res.status_code if res.status_code is not None else "error"
        msg = f"URL fetch failed (HTTP {sc}): {url}\n  {res.notes}"
        report(msg)
    plain = html_to_visible_text(res.text)
    lim = coalesce_per_url_limit(max_chars)
    if len(plain) > lim:
        plain = plain[:lim] + "\n\n[truncated]"
    try:
        write_cached_body(
            cache_dir,
            url,
            plain,
            http_status=res.status_code,
            notes=res.notes,
        )
    except OSError:
        pass
    return plain
