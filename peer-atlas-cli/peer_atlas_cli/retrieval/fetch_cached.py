"""HTTP fetch with optional disk cache."""

from __future__ import annotations

import pathlib
from collections.abc import Callable

from peer_atlas_cli.research import fetch_url_text_lenient
from peer_atlas_cli.retrieval.url_cache import (
    cache_dir_for_repo,
    read_cached_entry,
    write_cached_body,
)


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
        return text[:max_chars] if len(text) > max_chars else text
    if trace is not None:
        trace(f"fetch: network {url}")
    res = fetch_url_text_lenient(url, timeout=timeout, max_chars=max_chars)
    if report is not None and res.status_code != 200:
        sc = res.status_code if res.status_code is not None else "error"
        msg = f"URL fetch failed (HTTP {sc}): {url}\n  {res.notes}"
        report(msg)
    try:
        write_cached_body(
            cache_dir,
            url,
            res.text,
            http_status=res.status_code,
            notes=res.notes,
        )
    except OSError:
        pass
    return res.text[:max_chars] if len(res.text) > max_chars else res.text
