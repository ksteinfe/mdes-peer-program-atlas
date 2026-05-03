"""HTTP fetch with optional disk cache."""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from typing import TYPE_CHECKING

from peer_atlas_cli.fetch_limits import coalesce_per_url_limit, raw_download_cap
from peer_atlas_cli.html_text import html_to_visible_text
from peer_atlas_cli.research import fetch_url_text_lenient
from peer_atlas_cli.retrieval.url_cache import (
    cache_dir_for_repo,
    patch_cached_body_markdown,
    read_cached_entry,
    write_cached_body,
)

if TYPE_CHECKING:
    from peer_atlas_cli.llm_client import LLMClient


def _normalize_cached_html(text: str, *, max_chars: int) -> str:
    """Re-run simplifier on stored HTML (idempotent), then cap length."""
    plain = html_to_visible_text(text)
    lim = coalesce_per_url_limit(max_chars)
    if len(plain) > lim:
        return plain[:lim] + "\n\n[truncated]"
    return plain


def _cap_evidence_text(text: str, *, max_chars: int) -> str:
    lim = coalesce_per_url_limit(max_chars)
    if len(text) > lim:
        return text[:lim] + "\n\n[truncated]"
    return text


def _maybe_markdown_from_cache(
    entry: dict,
    *,
    url: str,
    cache_dir: pathlib.Path,
    max_chars: int,
    llm_client: "LLMClient | None",
    report: Callable[[str], None] | None,
) -> str | None:
    """Return capped markdown if present or successfully backfilled; else None."""
    md = entry.get("body_markdown")
    if isinstance(md, str) and md.strip():
        return _cap_evidence_text(md, max_chars=max_chars)
    if llm_client is None:
        return None
    body = entry.get("body")
    if not isinstance(body, str) or not body.strip():
        return None
    try:
        from peer_atlas_cli.retrieval.llm_evidence_markdown import (
            html_to_main_content_markdown,
            skip_html_markdown_llm,
        )

        if skip_html_markdown_llm():
            return None
        md_out = html_to_main_content_markdown(
            client=llm_client,
            cleaned_html=body,
            source_url=url,
        )
        if md_out.strip():
            patch_cached_body_markdown(cache_dir, url, md_out)
            return _cap_evidence_text(md_out, max_chars=max_chars)
    except Exception as e:
        if report is not None:
            report(f"html→markdown LLM failed (cached body) for {url}\n  {e}")
    return None


def fetch_url_text_cached(
    url: str,
    *,
    repo_root: pathlib.Path,
    timeout: float = 30.0,
    max_chars: int = 120_000,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
    llm_client: "LLMClient | None" = None,
) -> str:
    """Return main-content Markdown when available, else simplified HTML (legacy).

    If ``llm_client`` is set (and ``PEER_ATLAS_SKIP_HTML_MARKDOWN_LLM`` is not truthy),
    network fetches store ``body`` (simplified HTML) plus ``body_markdown`` in the URL
    cache JSON. Cached entries without ``body_markdown`` are backfilled on read.

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
        if report is not None:
            st = entry.get("http_status")
            if isinstance(st, int) and st != 200:
                notes = entry.get("notes")
                note_s = notes if isinstance(notes, str) else ""
                msg = f"URL fetch failed (cached HTTP {st}): {url}"
                if note_s.strip():
                    msg = f"{msg}\n  {note_s}"
                report(msg)
        md = _maybe_markdown_from_cache(
            entry,
            url=url,
            cache_dir=cache_dir,
            max_chars=max_chars,
            llm_client=llm_client,
            report=report,
        )
        if md is not None:
            return md
        body = entry.get("body")
        text = body if isinstance(body, str) else ""
        return _normalize_cached_html(text, max_chars=max_chars)
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
    md_out: str | None = None
    if llm_client is not None:
        try:
            from peer_atlas_cli.retrieval.llm_evidence_markdown import (
                html_to_main_content_markdown,
                skip_html_markdown_llm,
            )

            if not skip_html_markdown_llm():
                md_out = html_to_main_content_markdown(
                    client=llm_client,
                    cleaned_html=plain,
                    source_url=url,
                )
        except Exception as e:
            if report is not None:
                report(f"html→markdown LLM failed (network fetch) for {url}\n  {e}")
    try:
        write_cached_body(
            cache_dir,
            url,
            plain,
            http_status=res.status_code,
            notes=res.notes,
            body_markdown=md_out,
        )
    except OSError:
        pass
    if md_out and md_out.strip():
        return _cap_evidence_text(md_out, max_chars=max_chars)
    return plain
