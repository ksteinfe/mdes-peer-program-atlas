"""Run Tavily + evidence pipeline to build per-node EVIDENCE strings (Markdown excerpts)."""

from __future__ import annotations

import pathlib

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from peer_atlas_cli.llm_client import LLMClient

from peer_atlas_cli.cli_progress import cli_short_url
from peer_atlas_cli.retrieval.evidence_gathering_pipeline import (
    filter_hits_web_documents_only,
    is_non_web_document_url,
    search_urls_for_evidence,
)
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

# Tavily ``max_results`` per query for ingest nodes (positioning, duration, etc.).
DEFAULT_MAX_RESULTS_PER_QUERY_NODE = 10
# Narrower cap for per–core-course Tavily runs (several queries per row).
CORE_COURSE_MAX_RESULTS_PER_QUERY = 5


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


def _bundle_budget_unlimited(budget_chars: int) -> bool:
    """``<= 0`` disables the combined Markdown evidence cap for this bundle."""
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
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY_NODE,
    max_urls_total: int = 15,
    repo_root: pathlib.Path | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Tavily search (domain-scoped) + ranking; returns ``(urls, ranked_hits)`` (no fetch)."""
    queries = queries_for_node(
        node,
        program,
        seed_url=seed_url,
        user_query=user_query,
        repo_root=repo_root,
    )
    hits: list[dict[str, Any]] = []

    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        try:
            hits.extend(
                search_urls_for_evidence(
                    q,
                    seed_url=seed_url,
                    max_results=max_results_per_query,
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
    reg_domain = registered_domain_for_url(seed_url) if seed_url else None
    if node == "curriculum_overview" and reg_domain:
        hits = filter_hits_to_registered_domain(hits, reg_domain)

    urls = _dedupe_urls(
        [h["url"] for h in hits if isinstance(h.get("url"), str) and not is_non_web_document_url(str(h["url"]))]
    )[:max_urls_total]
    if node == "curriculum_overview" and reg_domain:
        urls = [
            u for u in urls if isinstance(u, str) and url_matches_registered_domain(u, reg_domain)
        ]
        urls = urls[:max_urls_total]

    if seed_url and not is_non_web_document_url(seed_url):
        if normalize_url(seed_url) not in {normalize_url(u) for u in urls}:
            if (not reg_domain) or (node != "curriculum_overview") or url_matches_registered_domain(
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
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY_NODE,
    max_urls_total: int = 15,
    repo_root: pathlib.Path | None = None,
) -> list[str]:
    """Ordered evidence URLs only (no fetch). See ``_evidence_urls_and_hits_for_node``."""
    urls, _hits = _evidence_urls_and_hits_for_node(
        node,
        program,
        seed_url=seed_url,
        user_query=user_query,
        max_results_per_query=max_results_per_query,
        max_urls_total=max_urls_total,
        repo_root=repo_root,
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
    llm_client: "LLMClient",
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
) -> list[tuple[str, str]]:
    """Fetch each URL via the evidence pipeline; returns ``(url, markdown)``."""
    out: list[tuple[str, str]] = []
    for url in urls:
        if not url or is_non_web_document_url(url):
            continue
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                llm_client=llm_client,
                report=report,
                trace=trace,
                warn_markdown_cap=report,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"fetch error · {cli_short_url(url)}: {e}")
        out.append((url, text))
    return out


def gather_evidence_for_node(
    node: str,
    program: dict[str, Any],
    *,
    llm_client: "LLMClient",
    repo_root: pathlib.Path,
    seed_url: str,
    user_query: str,
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY_NODE,
    max_urls_total: int = 15,
    budget_chars: int = 0,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
) -> str:
    """
    Domain-scoped Tavily search, fetch full Markdown per URL (evidence pipeline), then
    assemble one block for the LLM. ``budget_chars`` caps the combined **Markdown**
    excerpt size (including headers); ``<= 0`` means unlimited.
    """
    urls, hits = _evidence_urls_and_hits_for_node(
        node,
        program,
        seed_url=seed_url,
        user_query=user_query,
        max_results_per_query=max_results_per_query,
        max_urls_total=max_urls_total,
        repo_root=repo_root,
    )

    unlimited = _bundle_budget_unlimited(budget_chars)

    if trace is not None and urls:
        bud = "∞" if unlimited else str(budget_chars)
        trace(f"queue {len(urls)} urls · md budget {bud}")

    parts: list[str] = []
    used = 0
    for i, url in enumerate(urls):
        if not unlimited and used >= budget_chars:
            if trace is not None and i < len(urls):
                trace(f"skip {len(urls) - i} urls · md cap {budget_chars}")
            break
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                llm_client=llm_client,
                report=report,
                trace=trace,
                warn_markdown_cap=report,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"fetch error · {cli_short_url(url)}: {e}")
        header = f"\n\n=== SOURCE URL: {url} ===\n"
        chunk = header + text
        if not unlimited and used + len(chunk) > budget_chars:
            chunk = chunk[: max(0, budget_chars - used)] + "\n… [truncated for budget]\n"
        parts.append(chunk)
        used += len(chunk)

    if not parts and seed_url and not is_non_web_document_url(seed_url):
        try:
            t = fetch_url_text_cached(
                seed_url,
                repo_root=repo_root,
                llm_client=llm_client,
                report=report,
                trace=trace,
                warn_markdown_cap=report,
            )
            parts.append(f"\n\n=== SEED URL ONLY: {seed_url} ===\n{t}")
        except Exception as e:
            parts.append(f"\n\n=== SEED URL FAILED: {seed_url} ===\n{e}")
            if report is not None:
                report(f"fetch error · {cli_short_url(seed_url)}: {e}")

    snippets = []
    for h in hits[:15]:
        u, title = h.get("url"), h.get("title", "")
        c = str(h.get("content") or "")
        if u:
            snippets.append(f"- {title} — {u}\n  {c}")

    pre = (
        "Search snippets (Tavily):\n"
        + ("\n".join(snippets) if snippets else "(no search hits)")
        + "\n\nFetched page excerpts (Markdown):\n"
    )
    return pre + "".join(parts)


def gather_evidence_for_queries(
    queries: list[str],
    *,
    llm_client: "LLMClient",
    repo_root: pathlib.Path,
    seed_url: str = "",
    max_results_per_query: int = CORE_COURSE_MAX_RESULTS_PER_QUERY,
    max_urls_total: int = 15,
    budget_chars: int = 0,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
    program: dict[str, Any] | None = None,
    user_query: str = "",
    extra_anchor_phrases: list[str] | None = None,
    strict_anchor_filter: bool = False,
) -> str:
    """
    Ad-hoc evidence from explicit query strings (e.g. per core course).

    Default ``max_results_per_query`` is lower than ingest nodes because this path
    issues several Tavily calls per ``core_courses`` row.

    Tavily is scoped to ``seed_url``'s registrable domain when ``seed_url`` is set.
    ``budget_chars`` applies to the combined Markdown bundle only.
    """
    hits: list[dict[str, Any]] = []
    base = (seed_url or "").strip()
    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        try:
            if base:
                hits.extend(
                    search_urls_for_evidence(
                        q,
                        seed_url=base,
                        max_results=max_results_per_query,
                    )
                )
            else:
                hits.extend(
                    filter_hits_web_documents_only(
                        search_urls(q, max_results=max_results_per_query)
                    )
                )
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
    urls = _dedupe_urls(
        [h["url"] for h in hits if isinstance(h.get("url"), str) and not is_non_web_document_url(str(h["url"]))]
    )[:max_urls_total]
    if seed_url and not is_non_web_document_url(seed_url):
        urls = _dedupe_urls([seed_url] + urls)[:max_urls_total]

    unlimited = _bundle_budget_unlimited(budget_chars)

    if trace is not None and urls:
        bud = "∞" if unlimited else str(budget_chars)
        trace(f"queue {len(urls)} urls · md budget {bud}")

    parts: list[str] = []
    used = 0
    for i, url in enumerate(urls):
        if not unlimited and used >= budget_chars:
            if trace is not None and i < len(urls):
                trace(f"skip {len(urls) - i} urls · md cap {budget_chars}")
            break
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                llm_client=llm_client,
                report=report,
                trace=trace,
                warn_markdown_cap=report,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"fetch error · {cli_short_url(url)}: {e}")
        header = f"\n\n=== SOURCE URL: {url} ===\n"
        chunk = header + text
        if not unlimited and used + len(chunk) > budget_chars:
            chunk = chunk[: max(0, budget_chars - used)] + "\n… [truncated]\n"
        parts.append(chunk)
        used += len(chunk)
    return "".join(parts) if parts else "(no evidence fetched)"
