"""
Evidence gathering pipeline: scoped Tavily search → URL list → fetch raw HTML →
simplified HTML → main-body Markdown → URL cache JSON (with body / markdown char counts).

Does **not** build node ``EVIDENCE`` strings; callers apply ``evidence_budget_chars`` there.
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from peer_atlas_cli.cli_progress import cli_short_url
from peer_atlas_cli.html_text import html_to_visible_text
from peer_atlas_cli.research import fetch_url_text_lenient
from peer_atlas_cli.retrieval.host_scope import registered_domain_for_url
from peer_atlas_cli.retrieval.tavily_search import search_urls
from peer_atlas_cli.retrieval.url_cache import (
    cache_dir_for_repo,
    patch_cached_body_markdown,
    read_cached_entry,
    write_cached_body,
)

if TYPE_CHECKING:
    from peer_atlas_cli.llm_client import LLMClient

# Path/query hints for non-web documents (Tavily may still return these without filtering).
_NON_WEB_SUFFIXES: tuple[str, ...] = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".csv",
    ".rtf",
    ".odt",
    ".ods",
    ".odp",
)


def is_non_web_document_url(url: str) -> bool:
    """True if URL path (or last segment) looks like a downloadable office/PDF asset."""
    u = (url or "").strip().lower()
    if not u:
        return True
    try:
        path = urlparse(u).path or ""
    except ValueError:
        return True
    path = path.split("?", 1)[0].split("#", 1)[0]
    return any(path.endswith(sfx) for sfx in _NON_WEB_SUFFIXES)


def filter_hits_web_documents_only(hits: list[dict]) -> list[dict]:
    """Drop Tavily hits whose URL looks like PDF/DOC/etc."""
    out: list[dict] = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        u = h.get("url")
        if not isinstance(u, str) or not u.strip():
            continue
        if is_non_web_document_url(u):
            continue
        out.append(h)
    return out


def tavily_include_domains_for_seed_url(seed_url: str) -> list[str] | None:
    """
    Domains to pass to Tavily ``include_domains`` so results stay on the program site.

    Uses registrable domain (e.g. ``berkeley.edu``) when parseable; otherwise the
    request hostname if available.
    """
    u = (seed_url or "").strip()
    if not u:
        return None
    reg = registered_domain_for_url(u)
    if reg:
        return [reg]
    try:
        host = (urlparse(u).hostname or "").strip().lower()
        if host:
            return [host]
    except ValueError:
        pass
    return None


def search_urls_for_evidence(
    query: str,
    *,
    seed_url: str,
    max_results: int = 5,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """
    Tavily search restricted to the seed URL's registrable domain (or hostname),
    with PDF/office-style URLs removed from results.
    """
    domains = tavily_include_domains_for_seed_url(seed_url)
    raw = search_urls(
        query,
        max_results=max_results,
        timeout=timeout,
        include_domains=domains,
    )
    return filter_hits_web_documents_only(raw)


def fetch_simplify_markdown_and_store(
    url: str,
    *,
    repo_root: pathlib.Path,
    llm_client: "LLMClient",
    timeout: float = 30.0,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
    warn_markdown_cap: Callable[[str], None] | None = None,
) -> str:
    """
    Cache hit: return stored ``body_markdown`` (full string). Backfill markdown from
    cached ``body`` if missing.

    Cache miss: fetch unlimited raw HTML → simplified ``body`` → required Markdown
    LLM → write cache (``body_chars``, ``body_markdown_chars``), return markdown.

    ``llm_client`` is required whenever markdown must be produced (network or backfill).
    """
    from peer_atlas_cli.retrieval.llm_evidence_markdown import html_to_main_content_markdown

    cache_dir = cache_dir_for_repo(repo_root)
    entry = read_cached_entry(cache_dir, url)
    if entry is not None:
        su = cli_short_url(url)
        if trace is not None:
            trace(f"cache · {su}")
        if report is not None:
            st = entry.get("http_status")
            if isinstance(st, int) and st != 200:
                notes = entry.get("notes")
                note_s = notes if isinstance(notes, str) else ""
                msg = f"HTTP {st} (cached) · {su}"
                if note_s.strip():
                    msg = f"{msg} — {note_s.strip()[:120]}"
                report(msg)
        md = entry.get("body_markdown")
        if isinstance(md, str) and md.strip():
            return md
        body = entry.get("body")
        if isinstance(body, str) and body.strip():
            try:
                md_out = html_to_main_content_markdown(
                    client=llm_client,
                    cleaned_html=body,
                    source_url=url,
                    warn_input_cap=warn_markdown_cap,
                )
            except Exception as e:
                if report is not None:
                    report(f"html→md failed · {su}: {e}")
                raise
            if not (md_out or "").strip():
                raise RuntimeError(f"html→markdown LLM returned empty output for cached body: {url}")
            patch_cached_body_markdown(cache_dir, url, md_out)
            return md_out.strip()
        return ""

    su = cli_short_url(url)
    if trace is not None:
        trace(f"net · {su}")
    res = fetch_url_text_lenient(url, timeout=timeout)
    if report is not None and res.status_code != 200:
        sc = res.status_code if res.status_code is not None else "?"
        nn = (res.notes or "").strip()
        msg = f"HTTP {sc} · {su}"
        if nn:
            msg = f"{msg} — {nn[:120]}"
        report(msg)
    plain = html_to_visible_text(res.text)
    try:
        md_out = html_to_main_content_markdown(
            client=llm_client,
            cleaned_html=plain,
            source_url=url,
            warn_input_cap=warn_markdown_cap,
        )
    except Exception as e:
        if report is not None:
            report(f"html→md failed · {su}: {e}")
        raise
    if not (md_out or "").strip():
        raise RuntimeError(f"html→markdown LLM returned empty output for {url}")
    md_stripped = md_out.strip()
    try:
        write_cached_body(
            cache_dir,
            url,
            plain,
            http_status=res.status_code,
            notes=res.notes,
            body_markdown=md_stripped,
        )
    except OSError:
        pass
    return md_stripped
