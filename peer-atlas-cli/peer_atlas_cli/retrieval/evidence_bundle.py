"""Run Tavily + cached fetch to build evidence text for prompts."""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from typing import Any

from peer_atlas_cli.retrieval.fetch_cached import fetch_url_text_cached
from peer_atlas_cli.retrieval.query_builders import queries_for_node
from peer_atlas_cli.retrieval.tavily_search import search_urls
from peer_atlas_cli.retrieval.url_normalize import normalize_url


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        n = normalize_url(u)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(u)
    return out


def gather_evidence_for_node(
    node: str,
    program: dict[str, Any],
    *,
    repo_root: pathlib.Path,
    seed_url: str,
    user_query: str,
    max_results_per_query: int = 5,
    max_urls_total: int = 8,
    max_chars_per_url: int = 12_000,
    budget_chars: int = 48_000,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
) -> str:
    """
    Tavily search from node-specific queries, fetch top URLs (cached), return
    one markdown-ish block for the LLM.
    """
    queries = queries_for_node(node, program, seed_url=seed_url, user_query=user_query)
    hits: list[dict[str, Any]] = []
    for q in queries:
        try:
            hits.extend(
                search_urls(q, max_results=max_results_per_query)
            )
        except Exception:
            continue

    urls = _dedupe_urls([h["url"] for h in hits])[:max_urls_total]
    if seed_url and normalize_url(seed_url) not in {normalize_url(u) for u in urls}:
        urls.insert(0, seed_url)

    if trace is not None and urls:
        trace(f"evidence: will fetch {len(urls)} source URL(s)")

    parts: list[str] = []
    used = 0
    for url in urls:
        if used >= budget_chars:
            break
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                max_chars=max_chars_per_url,
                report=report,
                trace=trace,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"URL fetch failed (exception): {url}\n  {e}")
        header = f"\n\n=== SOURCE URL: {url} ===\n"
        chunk = header + text
        if used + len(chunk) > budget_chars:
            chunk = chunk[: budget_chars - used] + "\n… [truncated for budget]\n"
        parts.append(chunk)
        used += len(chunk)

    if not parts and seed_url:
        try:
            t = fetch_url_text_cached(
                seed_url,
                repo_root=repo_root,
                max_chars=max_chars_per_url,
                report=report,
                trace=trace,
            )
            parts.append(f"\n\n=== SEED URL ONLY: {seed_url} ===\n{t}")
        except Exception as e:
            parts.append(f"\n\n=== SEED URL FAILED: {seed_url} ===\n{e}")
            if report is not None:
                report(f"URL fetch failed (exception): {seed_url}\n  {e}")

    snippets = []
    for h in hits[:15]:
        u, title = h.get("url"), h.get("title", "")
        c = (h.get("content") or "")[:800]
        if u:
            snippets.append(f"- {title} — {u}\n  {c}")

    pre = (
        "Search snippets (Tavily):\n"
        + ("\n".join(snippets) if snippets else "(no search hits)")
        + "\n\nFetched page excerpts:\n"
    )
    return pre + "".join(parts)


def gather_evidence_for_queries(
    queries: list[str],
    *,
    repo_root: pathlib.Path,
    seed_url: str = "",
    max_results_per_query: int = 4,
    max_urls_total: int = 5,
    max_chars_per_url: int = 10_000,
    budget_chars: int = 32_000,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
) -> str:
    """Ad-hoc evidence from explicit query strings (e.g. per core course)."""
    hits: list[dict[str, Any]] = []
    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        try:
            hits.extend(search_urls(q, max_results=max_results_per_query))
        except Exception:
            continue
    urls = _dedupe_urls([h["url"] for h in hits])[:max_urls_total]
    if seed_url:
        urls = _dedupe_urls([seed_url] + urls)[:max_urls_total]

    if trace is not None and urls:
        trace(f"evidence: will fetch {len(urls)} source URL(s)")

    parts: list[str] = []
    used = 0
    for url in urls:
        if used >= budget_chars:
            break
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                max_chars=max_chars_per_url,
                report=report,
                trace=trace,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"URL fetch failed (exception): {url}\n  {e}")
        header = f"\n\n=== SOURCE URL: {url} ===\n"
        chunk = header + text
        if used + len(chunk) > budget_chars:
            chunk = chunk[: budget_chars - used] + "\n… [truncated]\n"
        parts.append(chunk)
        used += len(chunk)
    return "".join(parts) if parts else "(no evidence fetched)"
