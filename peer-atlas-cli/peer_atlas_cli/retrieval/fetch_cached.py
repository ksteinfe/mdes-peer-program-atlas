"""HTTP fetch with disk cache — delegates to the evidence gathering pipeline."""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from typing import TYPE_CHECKING

from peer_atlas_cli.retrieval.evidence_gathering_pipeline import fetch_simplify_markdown_and_store

if TYPE_CHECKING:
    from peer_atlas_cli.llm_client import LLMClient


def fetch_url_text_cached(
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
    Return full cached or freshly fetched **main-body Markdown** for ``url``.

    Raw HTML and simplified HTML are never truncated in this layer; the html→markdown
    model may receive a truncated *input* per ``PEER_ATLAS_HTML_MARKDOWN_LLM_INPUT_CHARS``
    (see ``warn_markdown_cap``). Callers apply ``evidence_budget_chars`` when assembling
    multi-URL evidence strings.

    ``llm_client`` is **required** (Markdown conversion and cache backfill are mandatory).
    """
    return fetch_simplify_markdown_and_store(
        url,
        repo_root=repo_root,
        llm_client=llm_client,
        timeout=timeout,
        report=report,
        trace=trace,
        warn_markdown_cap=warn_markdown_cap,
    )
