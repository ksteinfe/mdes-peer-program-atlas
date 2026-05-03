"""Run Tavily + cached fetch to build evidence text for prompts."""

from __future__ import annotations

import pathlib

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from peer_atlas_cli.llm_client import LLMClient

from peer_atlas_cli.retrieval.evidence_relevance import (
    dedupe_hits_preserve_order,
    rank_hits_for_program,
)
from peer_atlas_cli.retrieval.fetch_cached import fetch_url_text_cached
from peer_atlas_cli.retrieval.host_scope import (
    filter_hits_to_registered_domain,
    registered_domain_for_url,
    url_matches_registered_domain,
)
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


def _effective_max_chars_per_url(max_chars_per_url: int) -> int:
    """``<= 0`` means no practical per-URL cap beyond the fetch implementation."""
    if max_chars_per_url <= 0:
        return 1_000_000
    return max_chars_per_url


def _bundle_budget_unlimited(budget_chars: int) -> bool:
    """``<= 0`` disables the cross-URL evidence string cap (each URL still uses per-URL max)."""
    return budget_chars <= 0


def _priority_curriculum_evidence_urls(urls: list[str]) -> list[str]:
    """
    Prefer degree requirements / curriculum-like paths before generic home or
    project showcase pages when building the curriculum evidence bundle.
    """

    def rank(u: str) -> tuple[int, str]:
        s = (u or "").lower()
        if "degreerequire" in s or "degree-requirement" in s:
            return (0, u)
        if "requirement" in s and ("degree" in s or "program" in s):
            return (1, u)
        if "curriculum" in s or "/courses" in s or "catalog" in s:
            return (2, u)
        if "/paths" in s or "pathway" in s:
            return (3, u)
        if "admission" in s:
            return (5, u)
        if "/projects/" in s or "/news/" in s or "/blog/" in s:
            return (8, u)
        return (4, u)

    return sorted(urls, key=rank)


def _evidence_urls_and_hits_for_node(
    node: str,
    program: dict[str, Any],
    *,
    seed_url: str,
    user_query: str,
    max_results_per_query: int = 5,
    max_urls_total: int = 8,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Tavily search + ranking + domain filters; returns ``(urls, ranked_hits)`` (no fetch)."""
    queries = queries_for_node(node, program, seed_url=seed_url, user_query=user_query)
    hits: list[dict[str, Any]] = []

    reg_domain = registered_domain_for_url(seed_url) if seed_url else None
    include_domains: list[str] | None = None
    if node == "curriculum_overview" and reg_domain:
        include_domains = [reg_domain]

    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        try:
            hits.extend(
                search_urls(
                    q,
                    max_results=max_results_per_query,
                    include_domains=include_domains,
                )
            )
        except Exception:
            continue

    hits = rank_hits_for_program(
        hits,
        program,
        seed_url=seed_url,
        user_query=user_query,
        strict_anchor_filter=False,
    )
    if node == "curriculum_overview" and reg_domain:
        hits = filter_hits_to_registered_domain(hits, reg_domain)
    urls = _dedupe_urls([h["url"] for h in hits])[:max_urls_total]
    if node == "curriculum_overview" and reg_domain:
        urls = [
            u for u in urls if isinstance(u, str) and url_matches_registered_domain(u, reg_domain)
        ]
        urls = urls[:max_urls_total]

    if seed_url and normalize_url(seed_url) not in {normalize_url(u) for u in urls}:
        if (not reg_domain) or (not node == "curriculum_overview") or url_matches_registered_domain(
            seed_url, reg_domain
        ):
            urls.insert(0, seed_url)

    if node == "curriculum_overview" and urls:
        urls = _priority_curriculum_evidence_urls(urls)

    return urls, hits


def resolve_evidence_urls_for_node(
    node: str,
    program: dict[str, Any],
    *,
    seed_url: str,
    user_query: str,
    max_results_per_query: int = 5,
    max_urls_total: int = 8,
) -> list[str]:
    """Ordered evidence URLs only (no fetch). See ``_evidence_urls_and_hits_for_node``."""
    urls, _hits = _evidence_urls_and_hits_for_node(
        node,
        program,
        seed_url=seed_url,
        user_query=user_query,
        max_results_per_query=max_results_per_query,
        max_urls_total=max_urls_total,
    )
    return urls


def mash_curriculum_source_summaries(url_and_dense_text: list[tuple[str, str]]) -> str:
    """
    Concatenate per-URL dense curriculum extracts for the in-memory mash passed to
    the ``curriculum_overview`` JSON prompt (not stored on the program record).
    """
    parts: list[str] = []
    for url, dense in url_and_dense_text:
        u = (url or "").strip()
        body = (dense or "").strip()
        if not body:
            continue
        parts.append(f"### Source: {u}\n\n{body}")
    if not parts:
        return ""
    return "\n\n---\n\n".join(parts)


def fetch_pages_for_urls(
    urls: list[str],
    *,
    repo_root: pathlib.Path,
    max_chars_per_url: int,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
    llm_client: LLMClient | None = None,
) -> list[tuple[str, str]]:
    """Fetch each URL (cached); returns parallel list of ``(url, text)``."""
    per_url = _effective_max_chars_per_url(max_chars_per_url)
    out: list[tuple[str, str]] = []
    for url in urls:
        if not url:
            continue
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                max_chars=per_url,
                report=report,
                trace=trace,
                llm_client=llm_client,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"URL fetch failed (exception): {url}\n  {e}")
        out.append((url, text))
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
    max_chars_per_url: int = 120_000,
    budget_chars: int = 0,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
    llm_client: LLMClient | None = None,
) -> str:
    """
    Tavily search from node-specific queries, fetch top URLs (cached), return
    one markdown-ish block for the LLM.

    ``budget_chars <= 0`` means **no cap** on the combined fetched excerpt size
    (URLs are still fetched one-by-one; each uses ``max_chars_per_url``).
    ``max_chars_per_url <= 0`` means use a very large per-URL ceiling (the fetch
    layer may still apply its own safety limit). Defaults: ``max_chars_per_url``
    120_000 (≥ 50_000 coalesces to the multi‑MiB fetch floor) and ``budget_chars``
    0 (unlimited bundle).
    """
    urls, hits = _evidence_urls_and_hits_for_node(
        node,
        program,
        seed_url=seed_url,
        user_query=user_query,
        max_results_per_query=max_results_per_query,
        max_urls_total=max_urls_total,
    )

    per_url = _effective_max_chars_per_url(max_chars_per_url)
    unlimited = _bundle_budget_unlimited(budget_chars)

    if trace is not None and urls:
        trace(
            f"evidence: queueing {len(urls)} source URL(s); "
            f"char budget {'unlimited' if unlimited else budget_chars} "
            f"(up to {per_url} chars per URL)"
        )

    parts: list[str] = []
    used = 0
    for i, url in enumerate(urls):
        if not unlimited and used >= budget_chars:
            if trace is not None and i < len(urls):
                trace(
                    f"evidence: not fetching remaining {len(urls) - i} URL(s) "
                    f"(char budget {budget_chars} reached)"
                )
            break
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                max_chars=per_url,
                report=report,
                trace=trace,
                llm_client=llm_client,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"URL fetch failed (exception): {url}\n  {e}")
        header = f"\n\n=== SOURCE URL: {url} ===\n"
        chunk = header + text
        if not unlimited and used + len(chunk) > budget_chars:
            chunk = chunk[: budget_chars - used] + "\n… [truncated for budget]\n"
        parts.append(chunk)
        used += len(chunk)

    if not parts and seed_url:
        try:
            t = fetch_url_text_cached(
                seed_url,
                repo_root=repo_root,
                max_chars=per_url,
                report=report,
                trace=trace,
                llm_client=llm_client,
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
    max_chars_per_url: int = 120_000,
    budget_chars: int = 0,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
    program: dict[str, Any] | None = None,
    user_query: str = "",
    extra_anchor_phrases: list[str] | None = None,
    strict_anchor_filter: bool = False,
    llm_client: LLMClient | None = None,
) -> str:
    """
    Ad-hoc evidence from explicit query strings (e.g. per core course).

    Omit ``program`` for **per-course** research: hits are only deduped by URL,
    so registrar / catalog pages that do not mention the program name stay
    eligible. Pass ``program`` (+ optional anchors / strict) only for bundles
    where every hit should stay on-program (not the default for course search).

    Defaults match ``gather_evidence_for_node`` (``max_chars_per_url`` 120_000,
    ``budget_chars`` 0 = unlimited bundle).
    """
    hits: list[dict[str, Any]] = []
    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        try:
            hits.extend(search_urls(q, max_results=max_results_per_query))
        except Exception:
            continue
    if program is not None:
        hits = rank_hits_for_program(
            hits,
            program,
            seed_url=seed_url,
            user_query=user_query,
            strict_anchor_filter=strict_anchor_filter,
            extra_anchor_phrases=extra_anchor_phrases,
        )
    else:
        hits = dedupe_hits_preserve_order(hits)
    urls = _dedupe_urls([h["url"] for h in hits])[:max_urls_total]
    if seed_url:
        urls = _dedupe_urls([seed_url] + urls)[:max_urls_total]

    per_url = _effective_max_chars_per_url(max_chars_per_url)
    unlimited = _bundle_budget_unlimited(budget_chars)

    if trace is not None and urls:
        trace(
            f"evidence: queueing {len(urls)} source URL(s); "
            f"char budget {'unlimited' if unlimited else budget_chars} "
            f"(up to {per_url} chars per URL)"
        )

    parts: list[str] = []
    used = 0
    for i, url in enumerate(urls):
        if not unlimited and used >= budget_chars:
            if trace is not None and i < len(urls):
                trace(
                    f"evidence: not fetching remaining {len(urls) - i} URL(s) "
                    f"(char budget {budget_chars} reached)"
                )
            break
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                max_chars=per_url,
                report=report,
                trace=trace,
                llm_client=llm_client,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"URL fetch failed (exception): {url}\n  {e}")
        header = f"\n\n=== SOURCE URL: {url} ===\n"
        chunk = header + text
        if not unlimited and used + len(chunk) > budget_chars:
            chunk = chunk[: budget_chars - used] + "\n… [truncated]\n"
        parts.append(chunk)
        used += len(chunk)
    return "".join(parts) if parts else "(no evidence fetched)"
